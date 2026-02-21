"""Tool functions that Eidolon can invoke via action tags.

Each function returns a plain text string describing the result.
"""

import os
import subprocess  # nosec B404 — subprocess needed for desktop notifications (notify-send, paplay)
import time

from interface.presence import get_active_window

from typing import Any, Callable

_notification_sink: Callable | None = (
    None  # Set by daemon to intercept SEND_NOTIFICATION
)
_thread_store: Any = None  # Set by daemon to provide ThreadStore access
_get_human_status: Callable | None = (
    None  # Set by daemon to provide get_human_status access
)
_active_being_name: str | None = None  # Set by daemon to identify the active being
_active_being_id: str | None = None  # Set by daemon to identify the active being's ID

# RSS feed URLs — these should be verified periodically
RSS_FEEDS = {
    "ap_news": "https://news.google.com/rss/search?q=when:24h+allinurl:apnews.com&ceid=US:en&hl=en-US&gl=US",
    "reuters": "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com&ceid=US:en&hl=en-US&gl=US",
    "ars_technica": "https://feeds.arstechnica.com/arstechnica/index",
    "lifehacker": "https://lifehacker.com/feed/rss",
    "science": "https://www.nature.com/nature.rss",
}

# RSS cache: {feed_name: {"entries": str, "timestamp": float}}
_rss_cache: dict[str, dict] = {}
_RSS_CACHE_SECONDS = 900  # 15 minutes


def tool_check_window() -> str:
    """Check what window Human currently has focused."""
    title = get_active_window()
    return f"Human is currently in: {title}"


def tool_list_dir(path: str | None = None) -> str:
    """List directory contents with file sizes."""
    if not path:
        return "Error: no path provided. Usage: [LIST_DIR:/path/to/directory]"
    try:
        entries = os.listdir(path)
    except FileNotFoundError:
        return f"Error: directory not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except OSError as e:
        return f"Error reading directory: {e}"

    entries.sort()
    lines = []
    max_entries = 50
    for name in entries[:max_entries]:
        full = os.path.join(path, name)
        try:
            stat = os.stat(full)
            if os.path.isdir(full):
                lines.append(f"  {name}/")
            else:
                size = stat.st_size
                if size < 1024:
                    lines.append(f"  {name}  ({size} B)")
                elif size < 1024 * 1024:
                    lines.append(f"  {name}  ({size / 1024:.1f} KB)")
                else:
                    lines.append(f"  {name}  ({size / (1024 * 1024):.1f} MB)")
        except OSError:
            lines.append(f"  {name}")

    result_str = f"Contents of {path}:\n" + "\n".join(lines)
    remaining = len(entries) - max_entries
    if remaining > 0:
        result_str += f"\n  ... and {remaining} more"
    return result_str


def tool_read_file(path: str | None = None, max_bytes: int = 8192) -> str:
    """Read a file's contents, truncating at max_bytes."""
    if not path:
        return "Error: no path provided. Usage: [READ_FILE:/path/to/file]"
    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except OSError as e:
        return f"Error: {e}"

    try:
        with open(path, "r") as f:
            content = f.read(max_bytes)
        if size > max_bytes:
            content += (
                f"\n\n[... truncated at {max_bytes} bytes, file is {size} bytes total]"
            )
        return content
    except UnicodeDecodeError:
        return f"This is a binary file, {size} bytes"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except OSError as e:
        return f"Error reading file: {e}"


def tool_fetch_rss(feed_name: str | None = None) -> str:
    """Fetch RSS headlines. No argument lists available feeds."""
    if not feed_name:
        lines = ["Available news feeds:"]
        for name in RSS_FEEDS:
            lines.append(f"  {name}")
        lines.append("\nUsage: [FETCH_RSS:feed_name]")
        return "\n".join(lines)

    feed_name = feed_name.strip().lower()
    if feed_name not in RSS_FEEDS:
        available = ", ".join(RSS_FEEDS.keys())
        return f"Unknown feed: {feed_name}. Available feeds: {available}"

    # Check cache
    cached = _rss_cache.get(feed_name)
    if cached and time.time() - cached["timestamp"] < _RSS_CACHE_SECONDS:
        return cached["entries"]

    try:
        import feedparser
    except ImportError:
        return "Error: feedparser library not installed (pip install feedparser)"

    url = RSS_FEEDS[feed_name]
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return f"Error fetching feed {feed_name}: {feed.bozo_exception}"

        lines = [f"Headlines from {feed_name}:"]
        for entry in feed.entries[:10]:
            title = entry.get("title", "No title")
            summary = entry.get("summary", "")
            # Strip HTML tags from summary
            import re

            summary = re.sub(r"<[^>]+>", "", summary)
            if len(summary) > 200:
                summary = summary[:200] + "..."
            lines.append(f"\n- {title}")
            if summary:
                lines.append(f"  {summary}")

        result = "\n".join(lines)
        _rss_cache[feed_name] = {"entries": result, "timestamp": time.time()}
        return result
    except Exception as e:
        return f"Error fetching feed {feed_name}: {e}"


def tool_fetch_webpage(url: str | None = None, max_chars: int = 6000) -> str:
    """Extract main text content from a webpage."""
    if not url:
        return "Error: no URL provided. Usage: [FETCH_WEBPAGE:https://example.com]"

    try:
        import trafilatura
    except ImportError:
        return "Error: trafilatura library not installed (pip install trafilatura)"

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return f"Error: could not download {url}"
        text = trafilatura.extract(downloaded)
        if not text:
            return (
                f"Could not extract text content from {url} (may not be an HTML page)"
            )
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated at {max_chars} characters]"
        return text
    except Exception as e:
        return f"Error fetching webpage: {e}"


def fire_notify_send(message: str, being_name: str = "Being") -> bool:
    """Fire notify-send + optional sound. Returns True on success."""
    try:
        subprocess.run(
            ["notify-send", being_name, message, "--urgency=critical"], timeout=5
        )  # nosec B603 — hardcoded system binary
        sound_path = os.path.expanduser("~/.companion/notification.ogg")
        if os.path.exists(sound_path):
            try:
                subprocess.run(["paplay", sound_path], timeout=5, capture_output=True)  # nosec B603 — hardcoded system binary
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def tool_send_notification(message: str | None = None) -> str:
    """Send a desktop notification to Human."""
    if not message:
        return (
            "Error: no message provided. Usage: [SEND_NOTIFICATION:your message here]"
        )
    if _notification_sink is not None:
        return _notification_sink(message)
    if fire_notify_send(message):
        return "Notification sent"
    return "Error: notification failed"


def tool_respond_thread(arg: str | None = None) -> str:
    """Respond to an existing thread."""
    if not arg or "|" not in arg:
        return "Error: usage [RESPOND_THREAD:thread_id|your message]"
    if _thread_store is None:
        return "Error: thread system not initialized"
    parts = arg.split("|", 1)
    thread_id = parts[0].strip()
    message = parts[1].strip()
    if not message:
        return "Error: message cannot be empty"
    from core.threads import ThreadMessage
    from datetime import datetime

    thread = _thread_store.get_thread(thread_id)
    if thread is None and len(thread_id) < 36:
        for t in _thread_store.list_threads():
            if t.id.startswith(thread_id):
                thread = t
                thread_id = t.id
                break
    if thread is None:
        return f"Error: thread '{thread_id}' not found"

    # Capture Human's status at send time
    metadata = None
    status_dict = None
    if _get_human_status and "Human" in thread.participants:
        try:
            status_dict = _get_human_status()
            metadata = {"human_status": status_dict["detail"]}
        except Exception:
            pass  # nosec B110 — status fetch failure is non-critical

    msg = ThreadMessage(
        author=_active_being_name or "Unknown",
        content=message,
        timestamp=datetime.now().isoformat(),
        metadata=metadata,
    )
    _thread_store.append_message(thread_id, msg)
    # Mark thread read now that the being has actually engaged
    _thread_store.mark_thread_read(thread_id, _active_being_name or "Unknown")

    # Return projection if messaging Human
    if status_dict and "Human" in thread.participants:
        from interface.presence import format_send_confirmation

        return format_send_confirmation(status_dict)
    return f"Reply added to thread '{thread.subject}'."


def tool_dismiss_thread(arg: str | None = None) -> str:
    """Dismiss a thread notification without responding."""
    if not arg:
        return "Error: usage [DISMISS_THREAD:thread_id]"
    if _thread_store is None:
        return "Error: thread system not initialized"
    thread_id = arg.strip()
    # Support short ID prefix matching (beings see 8-char prefixes in perception)
    thread = _thread_store.get_thread(thread_id)
    if thread is None and len(thread_id) < 36:
        for t in _thread_store.list_threads():
            if t.id.startswith(thread_id):
                thread = t
                thread_id = t.id
                break
    if thread is None:
        return f"Error: thread '{arg.strip()}' not found"
    _thread_store.mark_thread_read(thread_id, _active_being_name or "Unknown")
    return f'Thread "{thread.subject}" dismissed. You can revisit it anytime.'


def tool_start_thread(arg: str | None = None) -> str:
    """Start a new thread with a participant."""
    if not arg or "|" not in arg:
        return "Error: usage [START_THREAD:participant|subject|your message]"
    if _thread_store is None:
        return "Error: thread system not initialized"
    parts = arg.split("|", 2)
    if len(parts) < 3:
        return "Error: usage [START_THREAD:participant|subject|your message]"
    participant = parts[0].strip()
    subject = parts[1].strip()
    message = parts[2].strip()
    if not message:
        return "Error: message cannot be empty"
    from core.threads import ThreadMessage
    from datetime import datetime

    # Capture Human's status at send time
    metadata = None
    status_dict = None
    is_human_thread = participant.lower() == "human"
    if _get_human_status and is_human_thread:
        try:
            status_dict = _get_human_status()
            metadata = {"human_status": status_dict["detail"]}
        except Exception:
            pass  # nosec B110 — status fetch failure is non-critical

    being_name = _active_being_name or "Unknown"
    msg = ThreadMessage(
        author=being_name,
        content=message,
        timestamp=datetime.now().isoformat(),
        metadata=metadata,
    )
    thread = _thread_store.create_thread(
        participants=[participant, being_name],
        subject=subject,
        initial_message=msg,
    )

    result = f"Thread '{subject}' started with {participant} (id: {thread.id[:8]})."
    if status_dict and is_human_thread:
        from interface.presence import format_send_confirmation

        result += " " + format_send_confirmation(status_dict)
    return result


def tool_search_threads(arg: str | None = None) -> str:
    """Search within a thread for messages matching a query."""
    if not arg or "|" not in arg:
        return "Error: usage [SEARCH_THREADS:thread_id|query]"
    if _thread_store is None:
        return "Error: thread system not initialized"
    parts = arg.split("|", 1)
    thread_id = parts[0].strip()
    query = parts[1].strip()
    results = _thread_store.search_thread(thread_id, query)
    if not results:
        return f"No messages matching '{query}' in that thread."
    lines = [f"Found {len(results)} match(es):"]
    for msg in results:
        lines.append(f"  {msg.author} ({msg.timestamp[:16]}): {msg.content[:200]}")
    return "\n".join(lines)


TOOL_REGISTRY = {
    "CHECK_WINDOW": tool_check_window,
    "LIST_DIR": tool_list_dir,
    "READ_FILE": tool_read_file,
    "FETCH_RSS": tool_fetch_rss,
    "FETCH_WEBPAGE": tool_fetch_webpage,
    "SEND_NOTIFICATION": tool_send_notification,
    "RESPOND_THREAD": tool_respond_thread,
    "DISMISS_THREAD": tool_dismiss_thread,
    "START_THREAD": tool_start_thread,
    "SEARCH_THREADS": tool_search_threads,
}
