"""Presence detection — what Brandon is doing on his PC.

Requires xdotool and xprintidle to be installed:
    sudo apt install xdotool xprintidle

All functions degrade gracefully if tools are missing or fail.
"""

import enum
import subprocess  # nosec B404 — subprocess needed for desktop interaction (xdotool, loginctl)
from datetime import datetime

from core.config import (
    BRANDON_SLEEP_WINDOW_START,
    BRANDON_SLEEP_WINDOW_END,
    PRESENCE_TIMEOUT_MINUTES,
    CYCLE_DURATION_MINUTES,
)
from remote import run_on_desktop


class BrandonStatus(enum.Enum):
    PRESENT = "present"
    AWAY = "away"
    ASLEEP = "asleep"


def _in_sleep_window(now: datetime | None = None) -> bool:
    """Check if current time falls within Brandon's sleep window.

    Handles midnight crossing (e.g. 22:00-06:00).
    """
    if now is None:
        now = datetime.now()
    current = now.hour * 60 + now.minute
    start_h, start_m = map(int, BRANDON_SLEEP_WINDOW_START.split(":"))
    end_h, end_m = map(int, BRANDON_SLEEP_WINDOW_END.split(":"))
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m

    if start <= end:
        # No midnight crossing (e.g. 01:00-05:00)
        return start <= current < end
    else:
        # Midnight crossing (e.g. 22:00-06:00)
        return current >= start or current < end


# Projection strings: (time_range, cycle_range)
_PROJECTIONS = {
    BrandonStatus.PRESENT: (
        "within 30 min - 2.5 hrs",
        "~1-6 cycles",
    ),
    BrandonStatus.AWAY: (
        "within 3-6 hours",
        "~7-13 cycles",
    ),
    BrandonStatus.ASLEEP: (
        "not until morning (after 6 AM)",
        "~13-18 cycles",
    ),
}


def get_brandon_status() -> dict:
    """Return structured status with projection for reply timing.

    Returns dict with: status, idle_seconds, projection, detail, timestamp.
    """
    now = datetime.now()
    idle = get_idle_seconds()
    screen_locked = False

    # Check screen lock
    try:
        session_result = run_on_desktop(["loginctl", "list-sessions", "--no-legend"])
        for line in session_result.stdout.strip().split("\n"):
            parts = line.split()
            if not parts:
                continue
            lock_result = run_on_desktop(
                ["loginctl", "show-session", parts[0],
                 "-p", "LockedHint", "--value"]
            )
            if lock_result.stdout.strip() == "yes":
                screen_locked = True
                break
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Determine status
    timeout_seconds = PRESENCE_TIMEOUT_MINUTES * 60

    if screen_locked or idle >= timeout_seconds:
        if _in_sleep_window(now):
            status = BrandonStatus.ASLEEP
            detail = "Brandon is likely asleep (screen locked, sleep window)"
        else:
            status = BrandonStatus.AWAY
            if screen_locked:
                detail = "Brandon is away (screen locked)"
            else:
                minutes = int(idle / 60)
                detail = f"Brandon has been away for {minutes} minutes"
    else:
        status = BrandonStatus.PRESENT
        window = get_active_window()
        if idle < 120:
            detail = f"Brandon is at his PC, in {window}"
        else:
            minutes = int(idle / 60)
            detail = f"Brandon is at his PC (idle {minutes}m), in {window}"

    time_proj, cycle_proj = _PROJECTIONS[status]

    return {
        "status": status,
        "idle_seconds": idle,
        "projection": f"Reply {time_proj}",
        "cycle_projection": cycle_proj,
        "detail": detail,
        "timestamp": now.isoformat(),
    }


def format_send_confirmation(status_dict: dict) -> str:
    """Format a send confirmation with reply projection."""
    status = status_dict["status"]
    time_proj = status_dict["projection"]
    cycle_proj = status_dict["cycle_projection"]
    if status == BrandonStatus.PRESENT:
        state_str = "at his PC"
    elif status == BrandonStatus.ASLEEP:
        state_str = "likely asleep"
    else:
        state_str = "away"
    return (
        f"Message sent to Brandon. "
        f"He's currently {state_str} — reply expected {time_proj} ({cycle_proj})."
    )


def get_pending_replies(thread_store, being_name: str, current_status: dict) -> list[dict]:
    """Scan active threads with Brandon where we're awaiting his reply.

    Returns list of dicts with: thread_id, subject, last_message_author,
    elapsed_minutes, elapsed_cycles, status_at_send, status_now.
    """
    now = datetime.now()
    pending = []

    threads = thread_store.list_threads(participant=being_name, status="active")
    for thread in threads:
        if "Brandon" not in thread.participants:
            continue
        if not thread.messages:
            continue
        last_msg = thread.messages[-1]
        if last_msg.author == "Brandon":
            continue  # Brandon already replied
        # We sent the last message — awaiting Brandon's reply
        try:
            sent_at = datetime.fromisoformat(last_msg.timestamp)
            elapsed = (now - sent_at).total_seconds()
        except (ValueError, TypeError):
            elapsed = 0

        elapsed_minutes = int(elapsed / 60)
        elapsed_cycles = round(elapsed / (CYCLE_DURATION_MINUTES * 60), 1)

        # Extract status at send time from metadata
        status_at_send = None
        if last_msg.metadata and "brandon_status" in last_msg.metadata:
            status_at_send = last_msg.metadata["brandon_status"]

        pending.append({
            "thread_id": thread.id,
            "subject": thread.subject,
            "last_message_author": last_msg.author,
            "elapsed_minutes": elapsed_minutes,
            "elapsed_cycles": elapsed_cycles,
            "status_at_send": status_at_send,
            "status_now": current_status["detail"],
        })

    return pending


def get_active_window() -> str:
    """Return the title of the currently focused window, or 'unknown'."""
    try:
        result = run_on_desktop(["xdotool", "getactivewindow", "getwindowname"])
        title = result.stdout.strip()
        return title if title else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown"


def get_idle_seconds() -> float:
    """Return seconds since last user input, or 0.0 on failure."""
    try:
        result = run_on_desktop(["xprintidle"])
        ms = int(result.stdout.strip())
        return ms / 1000.0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return 0.0


def get_presence_status() -> str:
    """Return a human-readable string describing Brandon's presence."""
    # Check screen lock via loginctl
    try:
        # Find the first active session
        session_result = run_on_desktop(["loginctl", "list-sessions", "--no-legend"])
        sessions = session_result.stdout.strip().split("\n")
        for line in sessions:
            parts = line.split()
            if not parts:
                continue
            session_id = parts[0]
            lock_result = run_on_desktop(
                ["loginctl", "show-session", session_id,
                 "-p", "LockedHint", "--value"]
            )
            if lock_result.stdout.strip() == "yes":
                return "Brandon is away (screen locked)"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    idle = get_idle_seconds()
    window = get_active_window()

    if idle < 120:
        return f"Brandon is at his PC, in {window}"
    elif idle < 600:
        minutes = int(idle / 60)
        return f"Brandon has been idle for {minutes} minutes (last seen in {window})"
    else:
        return "Brandon is away from his PC"


def is_brandon_away() -> bool:
    """Return True if Brandon is away (screen locked or idle >= 10 min)."""
    try:
        result = run_on_desktop(["loginctl", "list-sessions", "--no-legend"])
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if not parts:
                continue
            lock = run_on_desktop(
                ["loginctl", "show-session", parts[0], "-p", "LockedHint", "--value"]
            )
            if lock.stdout.strip() == "yes":
                return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return get_idle_seconds() >= 600
