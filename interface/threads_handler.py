"""Thread engagement and response handling — extracted from companion_daemon."""

import asyncio
import logging
from datetime import datetime

from brain.perception import build_perception
from brain.context import assemble_thread_context
from brain.inner_voice import run_layer1_reflexes, run_layer2_heuristics
from core.threads import ThreadMessage
from core.relationships import load_relationship
from inner_voices import word_overlap_ratio, run_hot_voice
from core.config import (
    INNER_VOICE_MAX_RETRIES,
    HOT_VOICE_LOOKBACK_COUNT,
    HOT_VOICE_SIMILARITY_THRESHOLD,
)

logger = logging.getLogger("companion_daemon")

# PROJECT_ROOT accessed via daemon.project_root


def is_duplicate_thread_response(daemon, thread_id: str, reply: str) -> bool:
    """Check if reply is too similar to a previous response in this thread."""
    recent = daemon._thread_response_history.get(thread_id, [])
    for prev in recent[-5:]:
        if word_overlap_ratio(reply, prev) >= 0.70:
            return True
    return False


def record_thread_response(daemon, thread_id: str, reply: str) -> None:
    """Record a thread response for future dedup checks."""
    if thread_id not in daemon._thread_response_history:
        daemon._thread_response_history[thread_id] = []
    daemon._thread_response_history[thread_id].append(reply)
    # Keep only last 10 per thread
    daemon._thread_response_history[thread_id] = daemon._thread_response_history[
        thread_id
    ][-10:]


async def engage_thread(daemon, thread_id: str, user_message: str) -> str:
    """Generate a being's reply to a thread through the full thought pipeline.

    Accesses: daemon._thread_store, daemon._active_being_name,
    daemon._active_memory_root, daemon.project_root, daemon._registry,
    daemon.fatigue, daemon.identity, daemon.personality, daemon.log_file,
    daemon._active_model
    Calls: daemon.generate_reply(), daemon._fatigue_label(), daemon._update_fatigue()
    """
    thread = daemon._thread_store.get_thread(thread_id)
    if thread is None:
        return "(Thread not found)"

    # Load relationship file for the other participant
    other = [p for p in thread.participants if p != daemon._active_being_name]
    rel_file = ""
    if other:
        rel_file = await asyncio.to_thread(
            load_relationship,
            daemon.project_root,
            daemon._active_memory_root,
            other[0],
        )

    # Build recent messages as chat history (enough context to ground the being)
    recent = thread.messages[-25:]
    recent_as_history = []
    for msg in recent:
        role = "assistant" if msg.author == daemon._active_being_name else "user"
        recent_as_history.append(
            {"role": role, "content": f"{msg.author}: {msg.content}"}
        )

    # Assemble thread context
    perception = await asyncio.to_thread(
        build_perception,
        thread_store=daemon._thread_store,
        being_name=daemon._active_being_name,
        registry=daemon._registry,
    )
    perception += (
        f"\n- Energy: {daemon._fatigue_label()} (fatigue {daemon.fatigue:.0%})"
    )

    messages, tokens_used = assemble_thread_context(
        perception=perception,
        identity=daemon.identity,
        personality=daemon.personality,
        relationship_file=rel_file,
        thread_summary=thread.summary,
        recent_messages=recent_as_history,
        user_message=user_message,
    )
    daemon._update_fatigue(tokens_used)

    # Generate reply
    try:
        reply = await daemon.generate_reply(messages)
    except Exception as e:
        logger.error("Thread reply generation error: %s", e)
        return f"(Couldn't generate a response — {e})"

    # Full inner voice Layer 1 checks
    for _ in range(INNER_VOICE_MAX_RETRIES):
        passed, correction = run_layer1_reflexes(
            reply,
            perception,
            daemon.identity,
            daemon.personality,
        )
        if passed:
            break
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": correction})
        try:
            reply = await daemon.generate_reply(messages)
        except Exception as e:
            logger.error("Inner voice retry error: %s", e)
            break

    # Hot voice — detect similarity loops against this being's prior thread messages
    own_prior = [
        m.content for m in thread.messages if m.author == daemon._active_being_name
    ][-HOT_VOICE_LOOKBACK_COUNT:]
    if own_prior and all(
        word_overlap_ratio(reply, prev) >= HOT_VOICE_SIMILARITY_THRESHOLD
        for prev in own_prior
    ):
        logger.info(
            "Thread hot voice fired for %s in thread %s",
            daemon._active_being_name,
            thread_id[:8],
        )
        hot_output = await asyncio.to_thread(run_hot_voice, reply)
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": hot_output})
        try:
            reply = await daemon.generate_reply(messages)
        except Exception as e:
            logger.error("Thread hot voice retry error: %s", e)

    # Layer 2 heuristic logging
    run_layer2_heuristics(reply, daemon.log_file)

    # Append reply to thread and mark read (being has engaged)
    daemon._thread_store.append_message(
        thread_id,
        ThreadMessage(
            author=daemon._active_being_name,
            content=reply,
            timestamp=datetime.now().isoformat(),
        ),
    )
    daemon._thread_store.mark_thread_read(thread_id, daemon._active_being_name)

    return reply


async def handle_thread_reply(daemon, msg: dict, writer: asyncio.StreamWriter) -> None:
    """Handle a thread reply request — full being pipeline.

    Always appends Human's message immediately.  If a being response
    is already being generated (lock held), returns a confirmation
    instead of blocking — the being will see all messages on its next cycle.

    Accesses: daemon._thread_store, daemon._thread_reply_lock,
    daemon._active_being_id, daemon._registry
    Calls: daemon._swap_being_context(), daemon._send()
    """
    being_name = msg.get("being", daemon._active_being_name)
    thread_id = msg.get("thread_id", "").strip()
    content = msg.get("content", "").strip()

    if not thread_id:
        await daemon._send(writer, {"type": "error", "content": "No thread_id."})
        return
    if not content:
        await daemon._send(writer, {"type": "error", "content": "No message content."})
        return
    if not daemon._thread_store:
        await daemon._send(
            writer, {"type": "error", "content": "Thread system not initialized."}
        )
        return

    # Resolve being
    chat_being = None
    if daemon._registry:
        chat_being = daemon._registry.get_being_by_name(being_name)
    if not chat_being:
        await daemon._send(
            writer, {"type": "error", "content": f"Unknown being: {being_name}"}
        )
        return

    # Always append Human's message immediately — never lose it
    daemon._thread_store.append_message(
        thread_id,
        ThreadMessage(
            author="Human",
            content=content,
            timestamp=datetime.now().isoformat(),
        ),
    )

    # Try to generate a being response — but don't block if busy
    if daemon._thread_reply_lock.locked():
        logger.info("Thread reply queued (being busy): %s", content[:80])
        await daemon._send(
            writer,
            {
                "type": "response",
                "content": f"(Message appended. {being_name} is still thinking — will see it next cycle.)",
                "being": being_name,
            },
        )
        return

    prev_being_id = daemon._active_being_id
    async with daemon._thread_reply_lock:
        try:
            await daemon._swap_being_context(chat_being)
            reply = await engage_thread(daemon, thread_id, content)
            await daemon._send(
                writer,
                {
                    "type": "response",
                    "content": reply,
                    "being": being_name,
                },
            )
        except Exception as e:
            logger.error("Thread reply error: %s", e)
            await daemon._send(writer, {"type": "error", "content": str(e)})
        finally:
            if daemon._registry and daemon._active_being_id != prev_being_id:
                prev_being = (
                    daemon._registry.get_being(prev_being_id) if prev_being_id else None
                )
                if prev_being:
                    await daemon._swap_being_context(prev_being)
