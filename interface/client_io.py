"""Client I/O pipeline — generate_reply and process_message extracted from companion_daemon."""

import asyncio
import logging

import ollama

from core.config import (
    TEMPERATURE,
    CONTEXT_WINDOW,
    RESPONSE_RESERVE,
    RETRIEVAL_TOP_K,
    INNER_VOICE_MAX_RETRIES,
    MEMORY_EXTRACTION_PROMPT,
    MEMORIES_FILE,
    EMBEDDING_MODEL,
    HOT_VOICE_LOOKBACK_COUNT,
    HOT_VOICE_SIMILARITY_THRESHOLD,
)
from brain.perception import build_perception
from brain.context import assemble_messages
from brain.inner_voice import run_layer1_reflexes, run_layer2_heuristics
from brain.conversation import save_turn
from brain.memory import extract_facts, save_facts
from brain.actions import resolve_actions_async
from core.stats import increment as stats_increment
from inner_voices import (
    should_cold_fire,
    run_cold_voice,
    run_hot_voice,
    cosine_similarity,
)

logger = logging.getLogger("companion_daemon")


async def generate_reply(
    daemon, messages: list[dict], *, num_predict: int = RESPONSE_RESERVE
) -> str:
    """Generate a reply from the active model.

    Accesses: daemon._active_model
    """
    response = await asyncio.to_thread(
        ollama.chat,
        model=daemon._active_model,
        messages=messages,
        stream=False,
        options={
            "temperature": TEMPERATURE,
            "num_ctx": CONTEXT_WINDOW,
            "num_predict": num_predict,
        },
    )
    return response["message"]["content"]


async def process_message(daemon, user_input: str) -> str:
    """Full turn pipeline — perception, retrieval, generation, inner voices, memory.

    Accesses: daemon._registry, daemon._active_being_name, daemon.fatigue,
    daemon.memory_index, daemon.identity, daemon.personality, daemon.human_facts,
    daemon.learned_facts, daemon.history, daemon.session_summaries,
    daemon._notified_this_cycle, daemon._active_being_id, daemon.log_file,
    daemon.session_filepath, daemon._active_model, daemon.project_root
    Calls: daemon._fatigue_label(), daemon._update_fatigue(), daemon.generate_reply()
    """
    # 1. Perception
    perception = await asyncio.to_thread(
        build_perception,
        registry=daemon._registry,
        being_name=daemon._active_being_name,
    )
    perception += (
        f"\n- Energy: {daemon._fatigue_label()} (fatigue {daemon.fatigue:.0%})"
    )

    # 2. Memory retrieval
    retrieved = await asyncio.to_thread(
        daemon.memory_index.search, user_input, RETRIEVAL_TOP_K
    )

    # 3. Assemble messages (pure function, no thread needed)
    messages, tokens_used = assemble_messages(
        perception,
        daemon.identity,
        daemon.personality,
        daemon.human_facts,
        daemon.learned_facts,
        daemon.history,
        user_input,
        daemon.session_summaries,
        retrieved_memories=retrieved,
    )
    daemon._update_fatigue(tokens_used)

    # 4. Generate reply
    try:
        reply = await daemon.generate_reply(messages)
    except Exception as e:
        logger.error("Ollama error: %s", e)
        return f"(I couldn't think of a response — {e})"

    # 4b. Action tag resolution
    try:
        daemon._notified_this_cycle = False
        msg_count_before = len(messages)
        reply = await resolve_actions_async(
            reply,
            daemon.generate_reply,
            messages,
            already_notified_this_cycle=daemon._notified_this_cycle,
        )
        if len(messages) > msg_count_before:
            stats_increment(daemon.project_root, daemon._active_being_id, "tool_use")
    except Exception as e:
        logger.error("Action resolution error: %s", e)

    # 5. Layer 1: reflex checks with retry
    for _ in range(INNER_VOICE_MAX_RETRIES):
        passed, correction = run_layer1_reflexes(
            reply, perception, daemon.identity, daemon.personality
        )
        if passed:
            break
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": correction})
        try:
            reply = await daemon.generate_reply(messages)
        except Exception as e:
            logger.error("Ollama retry error: %s", e)
            break

    # 6. Layer 2: heuristic logging (never blocks)
    run_layer2_heuristics(reply, daemon.log_file)

    # 6b. Cold voice check on chat response
    try:
        retrieved_texts = [m["text"] if isinstance(m, dict) else m for m in retrieved]
        if should_cold_fire(
            reply, perception, retrieved_texts, being_name=daemon._active_being_name
        ):
            cold_output = await asyncio.to_thread(
                run_cold_voice, reply, perception, retrieved_texts
            )
            logger.info("Cold voice fired during chat: %s", cold_output[:120])
            # Regenerate with cold voice interjection prepended
            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "user",
                    "content": f"A rational part of you objects: {cold_output}",
                }
            )
            try:
                reply = await daemon.generate_reply(messages)
            except Exception as e:
                logger.error("Cold voice regeneration error: %s", e)
    except Exception as e:
        logger.error("Cold voice chat check error (non-blocking): %s", e)

    # 6c. Hot voice check — semantic similarity against recent assistant replies
    try:
        prior_assistant = [
            m["content"] for m in daemon.history if m["role"] == "assistant"
        ]
        if len(prior_assistant) >= 2:
            recent = prior_assistant[-HOT_VOICE_LOOKBACK_COUNT:]
            texts = [reply] + recent
            embed_response = await asyncio.to_thread(
                ollama.embed, model=EMBEDDING_MODEL, input=texts
            )
            vecs = embed_response["embeddings"]
            reply_vec = vecs[0]
            if any(
                cosine_similarity(reply_vec, vecs[i + 1])
                >= HOT_VOICE_SIMILARITY_THRESHOLD
                for i in range(len(recent))
            ):
                hot_output = await asyncio.to_thread(run_hot_voice, reply)
                logger.info("Hot voice fired during chat: %s", hot_output[:120])
                messages.append({"role": "assistant", "content": reply})
                messages.append(
                    {
                        "role": "user",
                        "content": f"A spontaneous part of you interjects: {hot_output}",
                    }
                )
                try:
                    reply = await daemon.generate_reply(messages)
                except Exception as e:
                    logger.error("Hot voice regeneration error: %s", e)
    except Exception as e:
        logger.error("Hot voice chat check error (non-blocking): %s", e)

    # 7. Append to history
    daemon.history.append({"role": "user", "content": user_input})
    daemon.history.append({"role": "assistant", "content": reply})

    # 8. Save turn
    try:
        await asyncio.to_thread(save_turn, daemon.session_filepath, user_input, reply)
    except Exception as e:
        logger.error("Conversation save error: %s", e)

    # 9-11. Extract and save facts, rebuild index if needed
    try:
        new_facts = await asyncio.to_thread(
            extract_facts,
            user_input,
            daemon._active_model,
            MEMORY_EXTRACTION_PROMPT,
            CONTEXT_WINDOW,
        )
        daemon.learned_facts = await asyncio.to_thread(
            save_facts,
            daemon._active_memory_root,
            MEMORIES_FILE,
            new_facts,
            daemon.learned_facts,
        )
        if new_facts:
            await asyncio.to_thread(daemon.memory_index.rebuild)
    except Exception as e:
        logger.error("Memory save error: %s", e)

    return reply
