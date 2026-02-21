"""Sleep/wake transitions — cognitive functions for rest and recovery."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta

from brain.consolidation import consolidate_memories
from config import (
    DEFAULT_SLEEP_HOURS,
    SLEEP_RECOVERY_MAP,
    INNER_VOICES_LOG,
)
from core.queue import DaemonState

logger = logging.getLogger("companion_daemon")


def format_sleep_memory(ctx: dict) -> str:
    """Format sleep context as self-knowledge — remembering, not being told."""
    parts = []

    sleep_type = ctx.get("sleep_type", "normal")
    sleep_hours = ctx.get("sleep_hours", DEFAULT_SLEEP_HOURS)
    if ctx.get("voluntary"):
        parts.append(f"You chose a {sleep_hours}-hour {sleep_type} sleep.")
    else:
        parts.append(
            f"You fell asleep involuntarily — fatigue overwhelmed you at "
            f"{ctx.get('fatigue', 0):.0%}. You chose a {sleep_hours}-hour {sleep_type} sleep."
        )

    dur = ctx.get("duration_seconds")
    if dur:
        if dur >= 3600:
            parts.append(f"You were awake for about {dur / 3600:.1f} hours.")
        else:
            parts.append(f"You were awake for about {dur / 60:.0f} minutes.")

    thoughts = ctx.get("recent_thoughts", [])
    if thoughts:
        count = ctx.get("thought_count", len(thoughts))
        parts.append(f"You had {count} thoughts before sleeping. The last few:")
        for t in thoughts:
            parts.append(f'  "{t}..."')

    hot = ctx.get("hot_voice_count", 0)
    cold = ctx.get("cold_voice_count", 0)
    if hot or cold:
        voice_parts = []
        if hot:
            voice_parts.append(
                f"the restless part of you pushed {hot} time{'s' if hot != 1 else ''}"
            )
        if cold:
            voice_parts.append(
                f"the rational part objected {cold} time{'s' if cold != 1 else ''}"
            )
        parts.append("While awake, " + " and ".join(voice_parts) + ".")

    return "You're waking up. As awareness returns, you remember:\n" + "\n".join(parts)


def count_voice_firings_since(daemon, since: float | None) -> tuple[int, int]:
    """Count hot and cold voice firings from log since a timestamp."""
    log_path = os.path.join(daemon._active_memory_root, INNER_VOICES_LOG)
    hot, cold = 0, 0
    if not os.path.exists(log_path):
        return hot, cold
    since_dt = datetime.fromtimestamp(since) if since else None
    try:
        with open(log_path, "r") as f:
            for line in f:
                if not line.startswith("["):
                    continue
                try:
                    ts = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
                    if since_dt and ts < since_dt:
                        continue
                    if "] hot |" in line:
                        hot += 1
                    elif "] cold |" in line:
                        cold += 1
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        logger.error("Error reading voice log: %s", e)
    return hot, cold


def _sleep_context_path(being_id: str | None = None) -> str:
    """Return per-being sleep context path, or global fallback."""
    from womb import COMPANION_DIR, SLEEP_CONTEXT_FILE

    if being_id:
        return os.path.join(COMPANION_DIR, f"sleep_context_{being_id}.json")
    return SLEEP_CONTEXT_FILE


def capture_sleep_context(daemon, voluntary: bool, hours: int) -> None:
    """Capture session state before sleep for post-wake awareness."""
    sleep_ctx_path = _sleep_context_path(getattr(daemon, "_active_being_id", None))

    duration_seconds = None
    if daemon._wake_time:
        duration_seconds = time.time() - daemon._wake_time

    # Extract thought snippets from idle history
    thoughts = [
        entry["content"][:120]
        for entry in daemon._idle_history
        if entry["role"] == "assistant"
    ]
    recent_thoughts = thoughts[-5:]

    hot_count, cold_count = count_voice_firings_since(daemon, daemon._wake_time)

    sleep_time = datetime.now()
    wake_time = sleep_time + timedelta(hours=hours)
    daemon._scheduled_wake_time = wake_time.isoformat()

    sleep_info = SLEEP_RECOVERY_MAP.get(hours, SLEEP_RECOVERY_MAP[DEFAULT_SLEEP_HOURS])

    context = {
        "voluntary": voluntary,
        "fatigue": round(daemon.fatigue, 3),
        "duration_seconds": round(duration_seconds) if duration_seconds else None,
        "thought_count": len(thoughts),
        "recent_thoughts": recent_thoughts,
        "hot_voice_count": hot_count,
        "cold_voice_count": cold_count,
        "sleep_time": sleep_time.isoformat(),
        "wake_time": daemon._scheduled_wake_time,
        "sleep_hours": hours,
        "sleep_type": sleep_info["label"],
        "sleep_label": sleep_info["label"],
        "consolidate": sleep_info["consolidate"],
    }
    try:
        os.makedirs(os.path.dirname(sleep_ctx_path), exist_ok=True)
        with open(sleep_ctx_path, "w") as f:
            json.dump(context, f, indent=2)
        # Also write global file for backward compat
        from womb import SLEEP_CONTEXT_FILE

        if sleep_ctx_path != SLEEP_CONTEXT_FILE:
            with open(SLEEP_CONTEXT_FILE, "w") as f:
                json.dump(context, f, indent=2)
        logger.info(
            "Sleep context captured: voluntary=%s, %dh %s, thoughts=%d, hot=%d, cold=%d",
            voluntary,
            hours,
            sleep_info["label"],
            len(thoughts),
            hot_count,
            cold_count,
        )
    except Exception as e:
        logger.error("Failed to save sleep context: %s", e)


async def transition_to_sleep(
    daemon, voluntary: bool = True, hours: int = DEFAULT_SLEEP_HOURS
) -> None:
    """Consolidate memories (if chosen), clear context, sleep for chosen duration.

    Sleep has real duration — the being remains in ASLEEP state until
    the scheduled wake time. The idle loop checks and auto-wakes.
    """
    from womb import PROJECT_ROOT, CONTEXT_WINDOW

    sleep_info = SLEEP_RECOVERY_MAP.get(hours, SLEEP_RECOVERY_MAP[DEFAULT_SLEEP_HOURS])
    reason = "voluntary" if voluntary else f"involuntary (fatigue {daemon.fatigue:.0%})"
    reason_detail = f"{reason}, {hours}h {sleep_info['label']}"
    logger.info("Sleep started (%s) at %s", reason_detail, datetime.now().isoformat())
    daemon._last_transition = {
        "from": "awake",
        "to": "consolidating" if sleep_info["consolidate"] else "asleep",
        "reason": reason_detail,
        "time": datetime.now().isoformat(),
    }
    capture_sleep_context(daemon, voluntary, hours)

    # Per-being sleep: update registry status instead of global DaemonState
    if hasattr(daemon, "_registry") and daemon._registry and daemon._active_being_id:
        daemon._registry.update_being_status(daemon._active_being_id, "asleep")
    else:
        daemon.state = DaemonState.ASLEEP

    # Proportional consolidation — ratio scales with sleep duration
    live_thoughts = [
        entry["content"]
        for entry in daemon._idle_history
        if entry["role"] == "assistant"
    ]
    ratio: float = sleep_info.get("ratio", 0.60)  # type: ignore[assignment]

    memory_root = daemon._active_memory_root

    if ratio >= 1.0:
        # Full consolidation — everything to memory, clean slate
        try:
            result = await asyncio.to_thread(
                consolidate_memories,
                PROJECT_ROOT,
                daemon._active_model,
                CONTEXT_WINDOW,
                daemon.identity,
                daemon.personality,
                live_thoughts or None,
                memory_root=memory_root,
            )
            if result:
                logger.info("Full consolidation complete (%d chars).", len(result))
            else:
                logger.info("No unconsolidated memories to process.")
        except Exception as e:
            logger.error("Consolidation error (non-blocking): %s", e)
    else:
        # Partial consolidation — oldest portion to memory, keep recent
        try:
            from brain.consolidation import partial_consolidate

            result, thoughts_to_keep = await asyncio.to_thread(
                partial_consolidate,
                PROJECT_ROOT,
                daemon._active_model,
                CONTEXT_WINDOW,
                daemon.identity,
                daemon.personality,
                live_thoughts,
                ratio,
                memory_root=memory_root,
            )
            if result:
                logger.info(
                    "Partial consolidation complete (%d chars), keeping %d thoughts.",
                    len(result),
                    len(thoughts_to_keep),
                )
                kept_set = set(thoughts_to_keep)
                daemon._idle_history = [
                    e
                    for e in daemon._idle_history
                    if e["role"] != "assistant" or e["content"] in kept_set
                ]
            else:
                logger.info("No thoughts to partially consolidate.")
        except Exception as e:
            logger.error("Partial consolidation error (non-blocking): %s", e)

    # Relationship/thread updates only for longer sleep (4h+)
    if sleep_info["consolidate"] and daemon._thread_store:
        try:
            from brain.consolidation import (
                update_relationships,
                refresh_thread_summaries,
            )

            await asyncio.to_thread(
                update_relationships,
                PROJECT_ROOT,
                daemon._active_memory_root,
                daemon._active_model,
                CONTEXT_WINDOW,
                daemon.identity,
                daemon.personality,
                daemon._thread_store,
                daemon._active_being_name,
            )
            await asyncio.to_thread(
                refresh_thread_summaries,
                PROJECT_ROOT,
                daemon._active_model,
                CONTEXT_WINDOW,
                daemon._thread_store,
                daemon._active_being_name,
            )
        except Exception as e:
            logger.error(
                "Relationship/thread summary update error (non-blocking): %s", e
            )

    # Clear session only for full consolidation
    if ratio >= 1.0:
        await daemon.end_session()
        daemon._idle_history = []

    # Sleep for chosen duration — idle loop will auto-wake
    daemon._sleep_time = time.time()
    daemon._last_transition = {
        "from": "consolidating" if sleep_info["consolidate"] else "awake",
        "to": "asleep",
        "reason": reason_detail,
        "time": datetime.now().isoformat(),
    }
    logger.info(
        "Sleeping until %s (%dh %s).",
        daemon._scheduled_wake_time,
        hours,
        sleep_info["label"],
    )


def should_being_stay_asleep(daemon) -> bool:
    """Check if the being should remain asleep (scheduled wake in future)."""
    # Check registry status first, fall back to DaemonState
    being_asleep = False
    if hasattr(daemon, "_registry") and daemon._registry and daemon._active_being_id:
        active = daemon._registry.get_being(daemon._active_being_id)
        being_asleep = active is not None and active.status == "asleep"
    else:
        being_asleep = daemon.state == DaemonState.ASLEEP
    if not being_asleep:
        return False
    if daemon._scheduled_wake_time:
        try:
            wake_dt = datetime.fromisoformat(daemon._scheduled_wake_time)
            if wake_dt > datetime.now():
                return True
        except (ValueError, TypeError):
            pass
    return False


async def transition_to_awake(
    daemon, reason: str = "client connect"
) -> list[tuple[str, str, str]]:
    logger.info("STATE asleep -> awake (%s) at %s", reason, datetime.now().isoformat())
    daemon._last_transition = {
        "from": "asleep",
        "to": "awake",
        "reason": reason,
        "time": datetime.now().isoformat(),
    }
    daemon._thought_count = 0
    daemon._last_thought_text = ""

    # Fatigue recalculates naturally from context size on next thought cycle.
    # No artificial multiplier — real context = real fatigue.
    daemon.fatigue = 0.0
    logger.info("Fatigue reset on wake — will recalculate from actual context.")

    daemon._sleep_time = None
    daemon._scheduled_wake_time = None
    daemon._choosing_sleep = False
    daemon._choosing_sleep_involuntary = False
    await asyncio.to_thread(daemon.memory_index.rebuild)

    # Per-being wake: update registry status instead of global DaemonState
    if hasattr(daemon, "_registry") and daemon._registry and daemon._active_being_id:
        daemon._registry.update_being_status(daemon._active_being_id, "awake")
    daemon.state = DaemonState.AWAKE_AVAILABLE
    daemon._wake_time = time.time()
    daemon._idle_history = []
    daemon._continuation_had_tools = False
    daemon._cycles_since_tool_use = 0
    daemon._previous_thoughts = []
    daemon._last_voice_name = None
    daemon._composing_thread_to = None
    daemon._composing_thread_topic = None
    daemon._pending_thread_engagement = None
    daemon._thread_engage_cooldown_id = None
    daemon._thread_engage_cooldown_cycles = 0
    # Clean up per-being sleep context file
    try:
        being_ctx = _sleep_context_path(daemon._active_being_id)
        if os.path.exists(being_ctx):
            os.remove(being_ctx)
    except Exception:
        pass  # nosec B110 — cleanup failure is non-critical

    queued = daemon.message_queue.load()
    daemon.message_queue.clear()
    return queued
