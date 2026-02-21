#!/usr/bin/env python3
"""Terminal monitor for the Eidolon daemon."""

import argparse
import asyncio
import json
import sys
from datetime import datetime

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7777

# ANSI colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def format_duration(seconds):
    """Human-readable duration from seconds."""
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_duration_since(iso_timestamp):
    """Human-readable duration since an ISO timestamp."""
    if not iso_timestamp:
        return None
    try:
        then = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now() - then
        return format_duration(delta.total_seconds())
    except (ValueError, TypeError):
        return None


def fatigue_bar(pct, width=20):
    """Render a fatigue bar: [████████░░░░] 82%"""
    filled = round(pct / 100 * width)
    empty = width - filled
    if pct >= 85:
        color = RED
    elif pct >= 50:
        color = YELLOW
    else:
        color = GREEN
    return f"{color}[{'█' * filled}{'░' * empty}]{RESET} {pct}%"


def render(data):
    """Render a single status frame to stdout."""
    state = data.get("state", "unknown")
    fatigue_pct = data.get("fatigue_pct", round(data.get("fatigue", 0) * 100))
    fatigue_label = data.get("fatigue_label", "")
    uptime = data.get("uptime_seconds")
    asleep_since = data.get("asleep_since")
    thought_count = data.get("thought_count", 0)
    last_thought = data.get("last_thought")
    last_transition = data.get("last_transition", {})
    notification_count = data.get("notification_count", 0)
    queued = data.get("queued_messages", 0)

    lines = []

    # State line
    if state == "asleep":
        state_color = YELLOW
        state_icon = "~"
    else:
        state_color = GREEN
        state_icon = "*"
    display_state = "Asleep" if state == "asleep" else "Awake"
    lines.append(f"  {state_color}{BOLD}{state_icon} {display_state}{RESET}  {DIM}{fatigue_label}{RESET}")

    # Fatigue bar
    lines.append(f"  Fatigue:  {fatigue_bar(fatigue_pct)}")

    # Uptime / sleep duration
    wake_time = data.get("wake_time")
    sleep_type = data.get("sleep_type")
    sleep_hours = data.get("sleep_hours")
    if state == "asleep" and wake_time:
        try:
            wake_dt = datetime.fromisoformat(wake_time)
            remaining = wake_dt - datetime.now()
            remaining_secs = max(0, int(remaining.total_seconds()))
            wake_hm = wake_dt.strftime("%H:%M")
            type_info = f"{sleep_hours}h {sleep_type}, " if sleep_type and sleep_hours else ""
            lines.append(f"  Asleep:   until {wake_hm} ({type_info}{format_duration(remaining_secs)} remaining)")
        except (ValueError, TypeError):
            lines.append("  Asleep:   wake time unknown")
    elif state == "asleep" and asleep_since:
        dur = format_duration_since(asleep_since)
        if dur:
            lines.append(f"  Asleep:   {dur} (since {asleep_since[:19]})")
        else:
            lines.append(f"  Asleep:   since {asleep_since[:19]}")
    elif uptime is not None:
        lines.append(f"  Uptime:   {format_duration(uptime)}")

    # Thought count
    lines.append(f"  Thoughts: {thought_count}")

    # Last thought preview
    if last_thought:
        preview = last_thought[:80]
        if len(last_thought) > 80:
            preview += "..."
        # Collapse newlines for display
        preview = preview.replace("\n", " ")
        lines.append(f"  Last:     {DIM}\"{preview}\"{RESET}")

    # Last transition
    if last_transition:
        tr_from = last_transition.get("from", "?")
        tr_to = last_transition.get("to", "?")
        tr_reason = last_transition.get("reason", "")
        tr_time = last_transition.get("time", "")
        tr_ago = format_duration_since(tr_time)
        tr_str = f"{tr_from} -> {tr_to}"
        if tr_reason:
            tr_str += f" ({tr_reason})"
        if tr_ago:
            tr_str += f" {DIM}{tr_ago} ago{RESET}"
        lines.append(f"  Transition: {tr_str}")

    # Notifications and queued messages
    parts = []
    if notification_count:
        parts.append(f"{notification_count} notification(s)")
    if queued:
        parts.append(f"{queued} queued msg(s)")
    if parts:
        lines.append(f"  Pending:  {', '.join(parts)}")

    return "\n".join(lines)


async def fetch_status(host, port):
    """Connect to daemon, send peek, return parsed response."""
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(json.dumps({"type": "peek"}).encode() + b"\n")
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=5.0)
    writer.close()
    await writer.wait_closed()
    if not line:
        return None
    return json.loads(line.decode())


async def run_once(host, port):
    try:
        data = await fetch_status(host, port)
    except ConnectionRefusedError:
        print(f"{RED}Connection refused{RESET} — daemon not running?", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"{RED}Connection error:{RESET} {e}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        print(f"{RED}No response from daemon.{RESET}", file=sys.stderr)
        sys.exit(1)

    print(render(data))


async def run_watch(host, port, interval):
    """Auto-refresh loop."""
    while True:
        # Clear screen (simple: move cursor to top-left, clear)
        sys.stdout.write("\033[H\033[2J")
        sys.stdout.write(f"{DIM}Eidolon Monitor  (every {interval}s, Ctrl-C to quit){RESET}\n")
        sys.stdout.write(f"{DIM}{'─' * 50}{RESET}\n")

        try:
            data = await fetch_status(host, port)
            if data:
                sys.stdout.write(render(data) + "\n")
            else:
                sys.stdout.write(f"{RED}No response.{RESET}\n")
        except ConnectionRefusedError:
            sys.stdout.write(f"{RED}Connection refused — daemon not running?{RESET}\n")
        except OSError as e:
            sys.stdout.write(f"{RED}Connection error: {e}{RESET}\n")
        except asyncio.TimeoutError:
            sys.stdout.write(f"{RED}Timeout waiting for response.{RESET}\n")

        now = datetime.now().strftime("%H:%M:%S")
        sys.stdout.write(f"{DIM}{'─' * 50}{RESET}\n")
        sys.stdout.write(f"{DIM}Updated: {now}{RESET}\n")
        sys.stdout.flush()

        await asyncio.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Eidolon daemon monitor")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Daemon host (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Daemon port (default: %(default)s)")
    parser.add_argument("--watch", action="store_true",
                        help="Auto-refresh every 5s")
    parser.add_argument("--interval", type=int, default=5,
                        help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    try:
        if args.watch:
            asyncio.run(run_watch(args.host, args.port, args.interval))
        else:
            asyncio.run(run_once(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
