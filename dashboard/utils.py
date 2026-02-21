"""Shared helpers for the womb dashboard."""

import json
import os
import socket
import sys
from datetime import datetime


def get_project_root() -> str:
    """Return absolute path to the project root (parent of dashboard/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_imports():
    """Add project root to sys.path so core/brain/interface imports work."""
    root = get_project_root()
    if root not in sys.path:
        sys.path.insert(0, root)


ensure_imports()

from core.config import DAEMON_PORT  # noqa: E402
from core.threads import ThreadStore  # noqa: E402


def get_thread_store() -> ThreadStore:
    """Return a ThreadStore instance."""
    threads_dir = os.path.join(get_project_root(), "data", "threads")
    os.makedirs(threads_dir, exist_ok=True)
    return ThreadStore(threads_dir)


def peek_daemon(host: str = "127.0.0.1", port: int = DAEMON_PORT) -> dict | None:
    """TCP peek to daemon. Returns parsed JSON response or None."""
    try:
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.sendall(json.dumps({"type": "peek"}).encode() + b"\n")
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            if data:
                return json.loads(data.decode().strip())
    except (ConnectionRefusedError, OSError, json.JSONDecodeError, TimeoutError):
        pass
    return None


def send_thread_reply(
    being: str,
    thread_id: str,
    content: str,
    host: str = "127.0.0.1",
    port: int = DAEMON_PORT,
) -> dict | None:
    """Send a thread reply to a being via the daemon. Returns response dict or None."""
    try:
        with socket.create_connection((host, port), timeout=60) as sock:
            sock.sendall(
                json.dumps(
                    {
                        "type": "thread_reply",
                        "being": being,
                        "thread_id": thread_id,
                        "content": content,
                    }
                ).encode()
                + b"\n"
            )
            sock.settimeout(60)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            if data:
                return json.loads(data.decode().strip())
    except (ConnectionRefusedError, OSError, TimeoutError, json.JSONDecodeError):
        pass
    return None


def send_daemon_command(
    command: str,
    host: str = "127.0.0.1",
    port: int = DAEMON_PORT,
) -> dict | None:
    """Send a command to the daemon and return the response."""
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(
                json.dumps({"type": "command", "command": command}).encode() + b"\n"
            )
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            if data:
                return json.loads(data.decode().strip())
    except (ConnectionRefusedError, OSError, json.JSONDecodeError, TimeoutError):
        pass
    return None


USER_CONFIG_FILE = os.path.join(get_project_root(), "data", "user_config.json")


def load_user_config() -> dict:
    """Load user config from data/user_config.json."""
    try:
        with open(USER_CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_user_config(config: dict) -> None:
    """Save user config to data/user_config.json."""
    os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
    with open(USER_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_user_name() -> str:
    """Return the configured user display name, defaulting to 'Human'."""
    return load_user_config().get("user_name", "") or "Human"


def get_total_cycles() -> int:
    """Read total thought cycles across all beings from stats.json. Never resets."""
    from core.stats import get_all_stats

    stats = get_all_stats(get_project_root())
    return sum(b.get("thoughts", 0) for b in stats.values())


def format_timestamp(iso_string: str) -> str:
    """Convert ISO timestamp to human-readable format."""
    if not iso_string:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_string)
        now = datetime.now()
        delta = now - dt
        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            mins = int(delta.total_seconds() / 60)
            return f"{mins}m ago"
        if delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours}h ago"
        if delta.days < 7:
            return f"{delta.days}d ago"
        return dt.strftime("%b %d, %Y %H:%M")
    except (ValueError, TypeError):
        return iso_string[:19] if len(iso_string) > 19 else iso_string


def format_timestamp_short(iso_string: str) -> str:
    """Short timestamp: 'Feb 17 14:00' style."""
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%b %d %H:%M")
    except (ValueError, TypeError):
        return iso_string[:16]


def list_files_in(directory: str) -> list[str]:
    """List files in a directory, returning sorted basenames. Empty list if missing."""
    if not os.path.isdir(directory):
        return []
    return sorted(os.listdir(directory))


def read_file_safe(path: str) -> str:
    """Read a file's contents, returning empty string on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""
