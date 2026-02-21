"""Notification lifecycle — queue and fire desktop notifications."""

import asyncio
import logging
import time
from datetime import datetime

from interface.presence import is_brandon_away, get_brandon_status
from interface.tools import fire_notify_send
from core.threads import ThreadMessage
from core.config import NOTIFICATION_CHECK_INTERVAL, NOTIFICATION_COOLDOWN

logger = logging.getLogger("companion_daemon")


def queue_notification(daemon, message: str) -> str:
    """Queue a notification for delivery when Brandon is at his PC.

    Accesses: daemon.pending_notifications, daemon._active_being_name,
    daemon.notification_seen, daemon._notified_this_cycle, daemon._thread_store
    """
    if any(n["message"] == message for n in daemon.pending_notifications):
        logger.info("Notification duplicate skipped: %s", message[:80])
        return "Notification already queued — will be delivered when Brandon is at his PC."
    daemon.pending_notifications.append({
        "being": daemon._active_being_name,
        "message": message,
    })
    daemon.notification_seen = False
    daemon._notified_this_cycle = True
    # Also persist to thread system with Brandon's status at send time
    try:
        if daemon._thread_store:
            metadata = None
            try:
                status_dict = get_brandon_status()
                metadata = {"brandon_status": status_dict["detail"]}
            except Exception:
                pass  # nosec B110 — status fetch failure is non-critical for notifications
            thread = daemon._thread_store.find_or_create_thread(
                [daemon._active_being_name, "Brandon"],
                subject=f"Message from {daemon._active_being_name}",
            )
            daemon._thread_store.append_message(
                thread.id,
                ThreadMessage(
                    author=daemon._active_being_name,
                    content=message,
                    timestamp=datetime.now().isoformat(),
                    metadata=metadata,
                ),
            )
    except Exception as e:
        logger.error("Failed to persist notification to thread: %s", e)
    logger.info("Notification queued (%s): %s", daemon._active_being_name, message[:80])
    return "Notification queued — will be delivered when Brandon is at his PC."


async def check_presence_and_notifications(daemon) -> None:
    """Check for presence changes and fire notifications. Non-blocking.

    Accesses: daemon._last_presence_away, daemon._idle_history,
    daemon._continuation_had_tools, daemon._cycles_since_tool_use,
    daemon._last_voice_name, daemon.pending_notifications,
    daemon.notification_seen, daemon._last_notification_check,
    daemon.notification_sent_at
    """
    try:
        current_away = await asyncio.to_thread(is_brandon_away)
        if current_away != daemon._last_presence_away:
            logger.info("Presence changed, starting fresh thought chain.")
            daemon._idle_history = []
            daemon._continuation_had_tools = False
            daemon._cycles_since_tool_use = 0
            daemon._last_voice_name = None
        daemon._last_presence_away = current_away
    except Exception:
        return

    # Notification lifecycle
    if daemon.pending_notifications and not daemon.notification_seen:
        now = time.monotonic()
        if now - daemon._last_notification_check >= NOTIFICATION_CHECK_INTERVAL:
            daemon._last_notification_check = now
            try:
                just_returned = not current_away and daemon._last_presence_away
                if not current_away:
                    cooldown_ok = (
                        daemon.notification_sent_at is None
                        or (now - daemon.notification_sent_at) >= NOTIFICATION_COOLDOWN
                    )
                    if cooldown_ok or just_returned:
                        entry = daemon.pending_notifications.pop(0)
                        being = entry["being"]
                        msg = entry["message"]
                        await asyncio.to_thread(fire_notify_send, msg, being)
                        daemon.notification_sent_at = now
            except Exception as e:
                logger.error("Notification check error: %s", e)
