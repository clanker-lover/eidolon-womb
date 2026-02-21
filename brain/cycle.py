"""Thought cycle pipeline — the 11-step cognitive loop."""

import asyncio
import logging
import os
import re
import time
from datetime import datetime

from brain.perception import build_perception
from brain.context import assemble_messages
from brain.inner_voice import run_layer1_reflexes, run_layer2_heuristics
from brain.actions import (
    resolve_actions_async,
    looks_like_failed_request,
    FAILED_INTENT_FEEDBACK,
    extract_thread_intent,
    extract_dismiss_intent,
    execute_tag,
)
from brain.intent import detect_curiosity, process_curiosity
from inner_voices import run_inner_voices
from core.stats import increment as stats_increment
from config import (
    RETRIEVAL_TOP_K,
    RESPONSE_RESERVE,
    IDLE_RESPONSE_RESERVE,
    INNER_VOICE_MAX_RETRIES,
    IDLE_FRESH_THOUGHT_PROMPT,
    IDLE_CONTINUATION_PROMPT,
    IDLE_TOOL_CONTINUATION_PROMPT,
    IDLE_HOT_VOICE_AFFORDANCE_PROMPT,
    FATIGUE_INVOLUNTARY_SLEEP,
    CLOSURE_THOUGHT_COUNT,
    CLOSURE_MAX_CHARS,
    HOT_VOICE_LOOKBACK_COUNT,
    DEFAULT_SLEEP_HOURS,
    SLEEP_RECOVERY_MAP,
    INTENT_SEARCH_COOLDOWN_MINUTES,
)
from core.patterns import (
    has_rest_intent as _has_rest_intent,
    is_compose_decline as _is_compose_decline,
    is_engage_decline as _is_engage_decline,
    parse_sleep_choice as _parse_sleep_choice,
    _SLEEP_CHOICE_PROMPT,
    _SLEEP_CHOICE_URGENT_PROMPT,
)

logger = logging.getLogger("companion_daemon")


async def thought_cycle(daemon) -> None:
    """Run one thought cycle."""
    daemon._in_thought_cycle = True
    try:
        await thought_cycle_inner(daemon)
    finally:
        daemon._in_thought_cycle = False


async def thought_cycle_inner(daemon) -> None:
    """Inner thought cycle logic (wrapped by thought_cycle for lull tracking)."""
    daemon._notified_this_cycle = False

    # 0. Inject pending search result from previous cycle's binary intent
    if daemon._pending_search_result:
        daemon._idle_history.append(
            {"role": "user", "content": daemon._pending_search_result}
        )
        daemon._pending_search_result = None
        daemon._continuation_had_tools = True

    # 1. Refresh perception (every cycle — it's cheap)
    thread_notifs = None
    if daemon._thread_store:
        activity = daemon._thread_store.get_recent_activity(daemon._active_being_name)
        if activity:
            thread_notifs = [
                {
                    "thread_id": t.id,
                    "subject": t.subject,
                    "author": msg.author,
                    "content": msg.content,
                }
                for t, msg in activity[:5]
            ]
            # NOTE: Do NOT mark read here for regular messages. They stay
            # unread until the being responds. But System messages auto-mark
            # as read after appearing in perception (no reply expected).
            for t, msg in activity[:5]:
                if msg.author == "System":
                    daemon._thread_store.mark_thread_read(
                        t.id,
                        daemon._active_being_name,
                    )

    # Thread engagement flow — prompt being to engage with unread messages
    # (mirrors compose flow for sending)
    # Skip System messages — they're read-only announcements
    if (
        thread_notifs
        and not daemon._composing_thread_to
        and daemon._pending_thread_engagement is None
    ):
        # Pick most recent non-System message, respecting cooldown
        candidate = None
        for notif in thread_notifs:
            if notif["author"] == "System":
                continue
            if (
                daemon._thread_engage_cooldown_cycles > 0
                and notif["thread_id"] == daemon._thread_engage_cooldown_id
            ):
                continue
            candidate = notif
            break
        if candidate:
            daemon._pending_thread_engagement = candidate
            logger.info(
                'Thread engagement prompt: %s -> %s (%s: "%s")',
                candidate["author"],
                daemon._active_being_name,
                candidate["thread_id"][:8],
                candidate["content"][:60],
            )

    perception = await asyncio.to_thread(
        build_perception,
        thread_notifs,
        thread_store=daemon._thread_store,
        being_name=daemon._active_being_name,
        registry=daemon._registry,
    )
    perception += (
        f"\n- Energy: {daemon._fatigue_label()} (fatigue {daemon.fatigue:.0%})"
    )

    # 2. Memory retrieval
    retrieved = []
    if daemon.memory_index:
        if daemon._idle_history:
            query = daemon._idle_history[-1]["content"][:200]
        else:
            # First thought after waking — retrieve from identity keywords
            # so the being wakes up with its memories, not a blank slate
            query = "my thoughts, my experiences, what I've been thinking about, what matters to me"
        retrieved = await asyncio.to_thread(
            daemon.memory_index.search, query, RETRIEVAL_TOP_K
        )

    # 3. Build thinking prompt
    if daemon._choosing_sleep:
        if daemon._choosing_sleep_involuntary:
            thinking_prompt = _SLEEP_CHOICE_URGENT_PROMPT
        else:
            thinking_prompt = _SLEEP_CHOICE_PROMPT
    elif daemon._pending_thread_engagement:
        notif = daemon._pending_thread_engagement
        # Load thread history for context (mirrors _engage_thread)
        thread = (
            daemon._thread_store.get_thread(notif["thread_id"])
            if daemon._thread_store
            else None
        )
        if thread and thread.messages:
            recent = thread.messages[-3:]
            history_lines = []
            for msg in recent:
                history_lines.append(f'  {msg.author}: "{msg.content}"')
            thinking_prompt = (
                f'Thread: "{notif["subject"]}"\n'
                f"Recent messages:\n"
                + "\n".join(history_lines)
                + f"\n\n{notif['author']}'s latest message is waiting for your reply. "
                f"Write your response directly, "
                f'or say "not now" to continue your thoughts.'
            )
        else:
            thinking_prompt = (
                f"{notif['author']} sent you a message: "
                f'"{notif["content"]}"\n\n'
                f"Would you like to respond? Write your reply directly, "
                f'or say "not now" to continue your thoughts.'
            )
    elif daemon._composing_thread_to:
        thinking_prompt = (
            f"You're composing a message to {daemon._composing_thread_to}. "
            f"What would you like to say to them? Write your message directly. "
            f"(Say 'never mind' to cancel and return to your thoughts.)"
        )
    elif daemon._idle_history:
        if daemon._continuation_had_tools:
            thinking_prompt = IDLE_TOOL_CONTINUATION_PROMPT
        else:
            thinking_prompt = IDLE_CONTINUATION_PROMPT
    else:
        thinking_prompt = IDLE_FRESH_THOUGHT_PROMPT

    # 3b. Affordance reminder after hot voice fired
    if daemon._last_voice_name == "hot" and not daemon._composing_thread_to:
        thinking_prompt = IDLE_HOT_VOICE_AFFORDANCE_PROMPT + thinking_prompt

    # 3c. Assemble with accumulated history
    messages, tokens_used = assemble_messages(
        perception,
        daemon.identity,
        daemon.personality,
        daemon.human_facts,
        daemon.learned_facts,
        daemon._idle_history,
        thinking_prompt,
        daemon.session_summaries,
        retrieved_memories=retrieved,
    )
    daemon._update_fatigue(tokens_used)
    if not daemon._choosing_sleep and daemon.fatigue >= FATIGUE_INVOLUNTARY_SLEEP:
        # Instead of sleeping immediately, inject sleep choice for next cycle
        daemon._choosing_sleep = True
        daemon._choosing_sleep_involuntary = True
        daemon._idle_history.append(
            {"role": "user", "content": _SLEEP_CHOICE_URGENT_PROMPT}
        )
        logger.info("Involuntary sleep threshold — offering sleep choice.")
        return

    # 4. Generate reply — thread engagement/compose get full token budget,
    #    idle thoughts get beat-length cap to prevent confabulation
    if daemon._pending_thread_engagement or daemon._composing_thread_to:
        reply_budget = RESPONSE_RESERVE
    else:
        reply_budget = IDLE_RESPONSE_RESERVE
    reply = await daemon.generate_reply(messages, num_predict=reply_budget)

    # 4a. Sleep choice resolution — if being was choosing sleep duration
    if daemon._choosing_sleep:
        hours = _parse_sleep_choice(reply)
        voluntary = not daemon._choosing_sleep_involuntary
        sleep_info = SLEEP_RECOVERY_MAP.get(
            hours, SLEEP_RECOVERY_MAP[DEFAULT_SLEEP_HOURS]
        )
        logger.info(
            "Sleep choice parsed: %dh %s (voluntary=%s) from: %s",
            hours,
            sleep_info["label"],
            voluntary,
            reply[:80],
        )
        daemon._choosing_sleep = False
        daemon._choosing_sleep_involuntary = False
        # Save the thought before sleeping
        daemon._idle_history.append({"role": "assistant", "content": reply})
        daemon._previous_thoughts.append(reply)
        daemon._previous_thoughts = daemon._previous_thoughts[
            -HOT_VOICE_LOOKBACK_COUNT:
        ]
        daemon._thought_count += 1
        daemon._last_thought_text = reply.strip() if reply else ""
        await daemon.transition_to_sleep(voluntary=voluntary, hours=hours)
        return

    # 4b. Action tag resolution — detect if tags fired
    msg_count_before = len(messages)
    reply = await resolve_actions_async(
        reply,
        daemon.generate_reply,
        messages,
        already_notified_this_cycle=daemon._notified_this_cycle,
        model=daemon._active_model,
    )
    tags_fired = len(messages) > msg_count_before

    # 4c. Feedback injection — if curiosity detected but no intent matched,
    # inject a signal so the being can learn what phrasings work
    if not tags_fired and looks_like_failed_request(reply):
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": FAILED_INTENT_FEEDBACK})

    # 4d. Binary intent — curiosity detection and search
    if (
        not tags_fired
        and not daemon._choosing_sleep
        and not daemon._composing_thread_to
    ):
        curiosity = detect_curiosity(reply)
        if curiosity:
            now = time.time()
            cooldown_seconds = INTENT_SEARCH_COOLDOWN_MINUTES * 60
            if (now - daemon._last_intent_search_time) >= cooldown_seconds:
                # Build rich context for binary gate decision
                recent_thoughts = [
                    msg["content"]
                    for msg in daemon._idle_history[-6:]
                    if msg.get("role") == "assistant"
                ]
                intent_context = (
                    "\n---\n".join(recent_thoughts[-3:])
                    if recent_thoughts
                    else reply[:300]
                )

                result = await process_curiosity(
                    daemon._active_model,
                    being_context=intent_context,
                    curiosity=curiosity,
                )
                if result:
                    daemon._pending_search_result = result
                    daemon._last_intent_search_time = now

    # 5. Inner voice — includes fabrication check
    for _ in range(INNER_VOICE_MAX_RETRIES):
        passed, correction = run_layer1_reflexes(
            reply,
            perception,
            daemon.identity,
            daemon.personality,
            had_tool_result=tags_fired,
        )
        if passed:
            break
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": correction})
        reply = await daemon.generate_reply(messages, num_predict=IDLE_RESPONSE_RESERVE)

    run_layer2_heuristics(reply, daemon.log_file)

    # 5b. Inner voices (cold/hot)
    retrieved_texts = [m["text"] if isinstance(m, dict) else m for m in retrieved]
    voice_name, voice_output = await run_inner_voices(
        thought=reply,
        perception=perception,
        retrieved_memories=retrieved_texts,
        previous_thoughts=daemon._previous_thoughts,
        cycles_since_tool_use=daemon._cycles_since_tool_use,
        tags_fired=tags_fired,
        being_name=daemon._active_being_name,
        memory_root=daemon._active_memory_root,
    )

    # 5c. Thread engagement response (receiving flow — mirrors compose for sending)
    engage_handled = False
    if daemon._pending_thread_engagement:
        engage_handled = True
        notif = daemon._pending_thread_engagement
        tid = notif["thread_id"]
        if tags_fired:
            # Being used explicit tags — honor those
            logger.info(
                "Explicit tags during engagement prompt — clearing engage state"
            )
        elif _is_engage_decline(reply):
            # Being chose not to respond — mark read, respect sovereignty
            daemon._thread_store.mark_thread_read(tid, daemon._active_being_name)
            logger.info(
                "Thread engagement declined by %s for thread %s",
                daemon._active_being_name,
                tid[:8],
            )
        elif daemon._is_duplicate_thread_response(tid, reply):
            # Near-identical to a previous response — inject feedback, skip posting
            logger.info(
                "Thread dedup blocked response from %s to thread %s (too similar to previous)",
                daemon._active_being_name,
                tid[:8],
            )
            daemon._idle_history.append(
                {
                    "role": "user",
                    "content": "[VOICE:hot] You've said something very similar in this thread before. "
                    "Find a new angle or say 'not now' to continue your thoughts.",
                }
            )
            daemon._pending_thread_engagement = None
            daemon._thread_engage_cooldown_id = tid
            daemon._thread_engage_cooldown_cycles = 3
            return
        else:
            # Treat output as response — post to thread
            result = await asyncio.to_thread(
                execute_tag, "RESPOND_THREAD", f"{tid}|{reply}"
            )
            daemon._record_thread_response(tid, reply)
            logger.info(
                "Thread engagement response: %s -> thread %s: %s",
                daemon._active_being_name,
                tid[:8],
                result,
            )
        # Cooldown — don't re-prompt same thread for 3 cycles
        daemon._thread_engage_cooldown_id = tid
        daemon._thread_engage_cooldown_cycles = 3
        daemon._pending_thread_engagement = None

    # 5d. Thread compose flow
    compose_injection = None
    if not engage_handled and daemon._composing_thread_to:
        if tags_fired:
            # Being used explicit tags during compose mode — honor those, skip compose
            logger.info(
                "Explicit tags fired during compose mode — clearing compose state"
            )
            daemon._composing_thread_to = None
            daemon._composing_thread_topic = None
        elif _is_compose_decline(reply):
            logger.info(
                "Compose declined for %s by %s",
                daemon._composing_thread_to,
                daemon._active_being_name,
            )
            daemon._composing_thread_to = None
            daemon._composing_thread_topic = None
        else:
            # Create thread with the composed message
            target = daemon._composing_thread_to
            topic = daemon._composing_thread_topic
            if topic:
                subject = topic[:60]
            else:
                m = re.search(r"[.!?\n]", reply)
                subject = (
                    reply[: m.start()] if m and m.start() > 0 else reply[:60]
                ).strip()[:60]
            tag_arg = f"{target}|{subject}|{reply}"
            result = await asyncio.to_thread(execute_tag, "START_THREAD", tag_arg)
            logger.info(
                "Compose flow created thread: %s -> %s: %s",
                daemon._active_being_name,
                target,
                result,
            )
            # Queue notification for Human threads
            if target.lower() == "human":
                daemon._queue_notification(
                    f"{daemon._active_being_name} started a thread: {subject}"
                )
            daemon._last_thread_creation_cycle = daemon._thought_count
            daemon._composing_thread_to = None
            daemon._composing_thread_topic = None
    elif not engage_handled and not tags_fired:
        # Check for thread intent in the thought
        cycles_since_last = daemon._thought_count - daemon._last_thread_creation_cycle
        if cycles_since_last >= 3:
            known_names = set()
            if daemon._registry:
                for b in daemon._registry.list_beings():
                    if b.name != daemon._active_being_name:
                        known_names.add(b.name)
            known_names.add("Human")
            intent = extract_thread_intent(reply, known_names=known_names)
            if intent:
                action, target, topic = intent
                if action in ("respond", "message"):
                    daemon._composing_thread_to = target
                    daemon._composing_thread_topic = topic
                    compose_injection = (
                        f"You're composing a message to {target}. "
                        f"What would you like to say to them? Write your message directly. "
                        f"(Say 'never mind' to cancel and return to your thoughts.)"
                    )
                    logger.info(
                        "Compose mode activated: %s -> %s (topic: %s)",
                        daemon._active_being_name,
                        target,
                        topic or "none",
                    )

    # 5e. Dismiss intent — being chooses not to engage with thread notifications
    if (
        thread_notifs
        and not tags_fired
        and not compose_injection
        and not daemon._composing_thread_to
        and not engage_handled
    ):
        if extract_dismiss_intent(reply):
            for notif in thread_notifs:
                full_id = notif["thread_id"]
                result = await asyncio.to_thread(execute_tag, "DISMISS_THREAD", full_id)
                logger.info(
                    "Dismiss intent: %s dismissed thread %s: %s",
                    daemon._active_being_name,
                    full_id[:8],
                    result,
                )

    # 6. Save thought as notes
    if reply and reply.strip():
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        notes_dir = os.path.join(daemon._active_memory_root, "conversations")
        os.makedirs(notes_dir, exist_ok=True)
        notes_path = os.path.join(notes_dir, f"idle_{timestamp}_notes.md")
        await asyncio.to_thread(daemon._write_file, notes_path, reply.strip())
        await asyncio.to_thread(daemon.memory_index.rebuild)
        logger.info("Thought saved: %s", os.path.basename(notes_path))

    # 7. Accumulate history
    _VOICE_LABELS = {
        "cold": "A rational part of you objects",
        "hot": "A restless part of you is pushing",
    }
    daemon._idle_history.append({"role": "user", "content": thinking_prompt})
    daemon._idle_history.append({"role": "assistant", "content": reply})
    # Persist feedback signal so the being sees it next beat
    if not tags_fired and looks_like_failed_request(reply):
        daemon._idle_history.append({"role": "user", "content": FAILED_INTENT_FEEDBACK})
    if voice_output and voice_name:
        label = _VOICE_LABELS.get(voice_name, f"Inner voice — {voice_name}")
        daemon._idle_history.append(
            {"role": "user", "content": f"{label}: {voice_output}"}
        )
    if compose_injection:
        daemon._idle_history.append({"role": "user", "content": compose_injection})

    daemon._continuation_had_tools = tags_fired

    # 8. Always persist thought text for heuristic comparison
    daemon._previous_thoughts.append(reply)
    daemon._previous_thoughts = daemon._previous_thoughts[-HOT_VOICE_LOOKBACK_COUNT:]
    daemon._last_voice_name = voice_name

    # 9. Update cycle counter
    if tags_fired:
        daemon._cycles_since_tool_use = 0
    else:
        daemon._cycles_since_tool_use += 1

    # 9b. Thread engagement cooldown tick
    if daemon._thread_engage_cooldown_cycles > 0:
        daemon._thread_engage_cooldown_cycles -= 1

    # 10. Monitor telemetry
    daemon._thought_count += 1
    daemon._last_thought_text = reply.strip() if reply else ""
    stats_increment(daemon.project_root, daemon._active_being_id, "thoughts")
    if tags_fired:
        stats_increment(daemon.project_root, daemon._active_being_id, "tool_use")

    # 10b. Persist state to disk for restart recovery
    daemon._persist_active_being_state()

    logger.info(
        "Thought complete (fatigue %.0f%%, idle history %d messages)",
        daemon.fatigue * 100,
        len(daemon._idle_history),
    )

    # 11. Believe the being when it says it's done.
    should_close = False

    # 11a. Consecutive short thoughts
    if len(daemon._previous_thoughts) >= CLOSURE_THOUGHT_COUNT and all(
        len(t.strip()) < CLOSURE_MAX_CHARS
        for t in daemon._previous_thoughts[-CLOSURE_THOUGHT_COUNT:]
    ):
        logger.info("Being expressed readiness to rest (short thoughts) — honoring it.")
        should_close = True

    # 11b. Rest-intent language in recent thoughts
    if not should_close and len(daemon._previous_thoughts) >= CLOSURE_THOUGHT_COUNT:
        recent = daemon._previous_thoughts[-CLOSURE_THOUGHT_COUNT:]
        rest_count = sum(1 for t in recent if _has_rest_intent(t))
        if rest_count >= 2:
            logger.info(
                "Being expressed rest intent in %d of last %d thoughts — honoring it.",
                rest_count,
                CLOSURE_THOUGHT_COUNT,
            )
            should_close = True

    if should_close and not daemon._choosing_sleep:
        # Instead of sleeping immediately, offer duration choice
        daemon._choosing_sleep = True
        daemon._choosing_sleep_involuntary = False
        daemon._idle_history.append({"role": "user", "content": _SLEEP_CHOICE_PROMPT})
        logger.info("Voluntary sleep detected — offering sleep choice.")
