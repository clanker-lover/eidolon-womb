"""Daemon socket server — client handling, dispatch, I/O."""

import asyncio
import json
import os
import time
from datetime import datetime

from womb import (
    PROJECT_ROOT,
    SLEEP_CONTEXT_FILE,
    THOUGHT_INTERVAL_SECONDS,
    _format_sleep_memory,
    logger,
)
from core.queue import DaemonState


async def _send(daemon, writer: asyncio.StreamWriter, data: dict) -> None:
    """Write JSON line to client."""
    try:
        writer.write(json.dumps(data).encode() + b"\n")
        await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        logger.warning("Broken pipe while sending to client.")


def _build_arrival_prompt(
    queued: list[tuple[str, str, str]], being_id: str | None = None
) -> str:
    """Build greeting prompt with sleep memory and queued messages."""
    from brain.sleep import _sleep_context_path

    parts = []

    # Load sleep memory (one-shot: consumed on read) — per-being path first, then global
    sleep_ctx_loaded = False
    for ctx_path in [_sleep_context_path(being_id), SLEEP_CONTEXT_FILE]:
        try:
            if ctx_path and os.path.exists(ctx_path):
                with open(ctx_path, "r") as f:
                    ctx = json.load(f)
                os.remove(ctx_path)
                if not sleep_ctx_loaded:
                    parts.append(_format_sleep_memory(ctx))
                    sleep_ctx_loaded = True
        except Exception:
            pass  # nosec B110 — sleep context load failure is non-critical

    parts.append("Human walks into the room.")
    if queued:
        parts.append("While you were asleep, you received these messages:")
        for ts, sender, msg in queued:
            parts.append(f"[{ts}] {sender}: {msg}")
    return "\n".join(parts)


async def _handle_peek(daemon, writer: asyncio.StreamWriter) -> None:
    """Handle peek request — return daemon status snapshot."""
    from brain.sleep import _sleep_context_path

    being_asleep = daemon.state == DaemonState.ASLEEP
    state_label = "asleep" if being_asleep else daemon.state.value

    now = time.time()
    uptime_seconds = round(now - daemon._wake_time) if daemon._wake_time else None
    asleep_since = None
    sleep_type = None
    sleep_hours = None
    if being_asleep:
        # Try per-being sleep context, then global
        for ctx_path in [
            _sleep_context_path(daemon._active_being_id),
            SLEEP_CONTEXT_FILE,
        ]:
            try:
                if ctx_path and os.path.exists(ctx_path):
                    with open(ctx_path, "r") as f:
                        ctx = json.load(f)
                    asleep_since = ctx.get("sleep_time")
                    sleep_type = ctx.get("sleep_type")
                    sleep_hours = ctx.get("sleep_hours")
                    break
            except Exception:
                pass  # nosec B110 — peek context load failure is non-critical
    response = {
        "type": "peek_response",
        "state": state_label,
        "fatigue": round(daemon.fatigue, 3),
        "fatigue_pct": round(daemon.fatigue * 100),
        "fatigue_label": daemon._fatigue_label(),
        "uptime_seconds": uptime_seconds,
        "asleep_since": asleep_since,
        "wake_time": daemon._scheduled_wake_time,
        "sleep_type": sleep_type,
        "sleep_hours": sleep_hours,
        "thought_count": daemon._thought_count,
        "last_thought": daemon._last_thought_text[:200]
        if daemon._last_thought_text
        else None,
        "last_transition": daemon._last_transition,
        "pending_notifications": [
            {"being": n["being"], "message": n["message"][:100]}
            for n in daemon.pending_notifications
        ],
        "notification_count": len(daemon.pending_notifications),
        "queued_messages": len(daemon.message_queue.load()),
        "thought_interval": THOUGHT_INTERVAL_SECONDS,
    }

    # Single-being data for dashboard consumption
    active_threads = 0
    if daemon._thread_store:
        active_threads = daemon._thread_store.count_active(
            participant=daemon._active_being_name
        )
    response["beings"] = [
        {
            "name": daemon._active_being_name,
            "status": "asleep" if daemon.state == DaemonState.ASLEEP else "awake",
            "model": daemon._active_model,
            "active_threads": active_threads,
            "fatigue": round(daemon.fatigue, 3),
            "thought_count": daemon._thought_count,
            "is_asleep": daemon.state == DaemonState.ASLEEP,
            "wake_time": daemon._scheduled_wake_time,
        }
    ]
    from core.stats import get_all_stats

    all_stats = get_all_stats(PROJECT_ROOT)
    response["total_cycles"] = sum(s.get("thoughts", 0) for s in all_stats.values())

    await _send(daemon, writer, response)
    logger.debug("Peek request served.")


async def handle_client(
    daemon,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Handle a client connection — greeting, message loop, departure."""
    # First message detection — peek, connect, or thread_reply
    try:
        first_line = await asyncio.wait_for(reader.readline(), timeout=0.3)
        if first_line:
            try:
                first_msg = json.loads(first_line.decode())
            except json.JSONDecodeError:
                first_msg = None
            if first_msg:
                if first_msg.get("type") == "peek":
                    await _handle_peek(daemon, writer)
                    writer.close()
                    await writer.wait_closed()
                    return
                if first_msg.get("type") == "thread_reply":
                    await daemon._handle_thread_reply(first_msg, writer)
                    writer.close()
                    await writer.wait_closed()
                    return
    except asyncio.TimeoutError:
        pass

    # Single-client enforcement
    if daemon._current_writer is not None:
        await _send(
            daemon,
            writer,
            {
                "type": "error",
                "content": "Another client is already connected.",
            },
        )
        writer.close()
        await writer.wait_closed()
        logger.warning("Rejected second client connection.")
        return

    daemon._current_writer = writer
    daemon._idle_can_run.clear()

    logger.info("Client connected.")

    # Wait for idle loop to finish if busy
    if daemon.state == DaemonState.AWAKE_BUSY:
        logger.info("Waiting for idle task to finish...")
        for _ in range(30):  # up to 30s
            if daemon.state != DaemonState.AWAKE_BUSY:
                break
            await asyncio.sleep(1)

    try:
        # Wake up if asleep — but respect scheduled sleep choices
        queued_messages: list[tuple[str, str, str]] = []
        if daemon.state == DaemonState.ASLEEP:
            if daemon._should_being_stay_asleep():
                # Being chose to sleep — don't override their choice
                wake_dt = datetime.fromisoformat(daemon._scheduled_wake_time)
                logger.info(
                    "Client connected during scheduled sleep (wake at %s). "
                    "Respecting sleep choice.",
                    daemon._scheduled_wake_time,
                )
                await _send(
                    daemon,
                    writer,
                    {
                        "type": "status",
                        "state": daemon.state.value,
                        "content": (
                            f"{daemon._active_being_name} is asleep."
                            f" Waking at {wake_dt.strftime('%H:%M')}."
                            f" Messages will be queued."
                            f" Use /wake to wake explicitly."
                        ),
                    },
                )
                # Skip session/greeting — enter message loop directly.
                # _dispatch queues messages; /wake command can override.
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        msg = json.loads(line.decode())
                    except json.JSONDecodeError:
                        await _send(
                            daemon,
                            writer,
                            {"type": "error", "content": "Invalid JSON."},
                        )
                        continue
                    await _dispatch(daemon, msg, writer)
                return  # finally block handles cleanup
            else:
                queued_messages = await daemon.transition_to_awake()

        # Start a new session
        await daemon.start_session()

        # Deliver pending notifications and clear them
        delivered_notifications = [
            {"being": n["being"], "message": n["message"]}
            for n in daemon.pending_notifications
        ]
        daemon.pending_notifications.clear()
        daemon.notification_seen = True
        daemon.notification_sent_at = None

        if delivered_notifications:
            await _send(
                daemon,
                writer,
                {
                    "type": "pending_notifications",
                    "notifications": delivered_notifications,
                },
            )

        # Process arrival — inject queued messages so the being reads them
        arrival = _build_arrival_prompt(
            queued_messages, being_id=daemon._active_being_id
        )
        greeting = await daemon.process_message(arrival)
        await _send(
            daemon,
            writer,
            {
                "type": "response",
                "content": greeting,
                "being": daemon._active_being_name,
            },
        )

        # Message loop
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode())
            except json.JSONDecodeError:
                await _send(
                    daemon, writer, {"type": "error", "content": "Invalid JSON."}
                )
                continue
            await _dispatch(daemon, msg, writer)

    except asyncio.CancelledError:
        logger.info("Client handler cancelled.")
    except Exception as e:
        logger.error("Client handler error: %s", e)
    finally:
        # Process departure (logged but not sent to client)
        if daemon.session_filepath and daemon.state == DaemonState.AWAKE_AVAILABLE:
            try:
                departure = await daemon.process_message("Human leaves the room.")
                logger.info("Departure response: %s", departure)
            except Exception as e:
                logger.error("Departure processing error: %s", e)
            await daemon.end_session()
        daemon._current_writer = None
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass  # nosec B110 — cleanup failure on disconnect is non-critical
        daemon._idle_can_run.set()
        logger.info("Client disconnected.")


async def _dispatch(daemon, msg: dict, writer: asyncio.StreamWriter) -> None:
    """Route incoming messages by type."""
    msg_type = msg.get("type")
    if msg_type == "message":
        content = msg.get("content", "").strip()
        if not content:
            return
        if daemon.state == DaemonState.ASLEEP:
            daemon.message_queue.append("Human", content)
            wake_info = ""
            if daemon._scheduled_wake_time:
                try:
                    wake_dt = datetime.fromisoformat(daemon._scheduled_wake_time)
                    wake_info = f" Waking at {wake_dt.strftime('%H:%M')}."
                except (ValueError, TypeError):
                    pass
            await _send(
                daemon,
                writer,
                {
                    "type": "queued",
                    "message": f"{daemon._active_being_name} is asleep.{wake_info} Message queued.",
                },
            )
        elif daemon.state == DaemonState.AWAKE_BUSY:
            daemon.message_queue.append("Human", content)
            await _send(
                daemon,
                writer,
                {
                    "type": "queued",
                    "message": f"{daemon._active_being_name} is busy. Message queued.",
                },
            )
        else:
            reply = await daemon.process_message(content)
            await _send(
                daemon,
                writer,
                {
                    "type": "response",
                    "content": reply,
                    "being": daemon._active_being_name,
                },
            )
            if await daemon._check_involuntary_sleep(writer):
                return
    elif msg_type == "command":
        await _handle_command(daemon, msg.get("command", ""), writer)
    else:
        await _send(
            daemon, writer, {"type": "error", "content": f"Unknown type: {msg_type}"}
        )


async def _handle_command(daemon, command: str, writer: asyncio.StreamWriter) -> None:
    """Process /commands from client."""
    if command == "sleep":
        if daemon.state == DaemonState.ASLEEP:
            await _send(
                daemon,
                writer,
                {
                    "type": "status",
                    "state": "asleep",
                    "content": "Already asleep.",
                },
            )
            return
        await daemon.transition_to_sleep()
        await _send(
            daemon,
            writer,
            {
                "type": "status",
                "state": daemon.state.value,
                "content": f"{daemon._active_being_name} is now asleep.",
            },
        )

    elif command == "wake":
        if daemon.state != DaemonState.ASLEEP:
            await _send(
                daemon,
                writer,
                {
                    "type": "status",
                    "state": daemon.state.value,
                    "content": "Already awake.",
                },
            )
            return
        queued = await daemon.transition_to_awake()
        await daemon.start_session()
        # Process re-arrival — being reads its queued messages
        arrival = _build_arrival_prompt(queued, being_id=daemon._active_being_id)
        greeting = await daemon.process_message(arrival)
        await _send(
            daemon,
            writer,
            {
                "type": "response",
                "content": greeting,
                "being": daemon._active_being_name,
            },
        )
        await _send(
            daemon,
            writer,
            {
                "type": "status",
                "state": daemon.state.value,
                "content": f"{daemon._active_being_name} is awake. {len(queued)} queued message(s).",
            },
        )

    elif command == "status":
        await _send(
            daemon,
            writer,
            {
                "type": "status",
                "state": daemon.state.value,
                "session_id": daemon.session_id,
                "history_length": len(daemon.history),
                "learned_facts_count": len(daemon.learned_facts),
                "fatigue": round(daemon.fatigue, 3),
                "fatigue_label": daemon._fatigue_label(),
                "pending_notifications": len(daemon.pending_notifications),
                "content": f"State: {daemon.state.value}, session: {daemon.session_id}, "
                f"turns: {len(daemon.history) // 2}, facts: {len(daemon.learned_facts)}, "
                f"fatigue: {daemon.fatigue:.0%} ({daemon._fatigue_label()})",
            },
        )

    else:
        await _send(
            daemon, writer, {"type": "error", "content": f"Unknown command: {command}"}
        )
