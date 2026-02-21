"""Inner voices — cold (rational correction) and hot (restless provocation).

Cold voice catches invented experiences that aren't grounded in perception or memory.
Hot voice breaks abstract philosophy loops by pushing toward concrete action.
Neither controls the being — they speak into the thought stream for the next cycle.
"""

import asyncio
import os
from datetime import datetime

import ollama

from config import (
    MODEL_NAME,
    CONTEXT_WINDOW,
    COLD_VOICE_TEMPERATURE,
    HOT_VOICE_TEMPERATURE,
    INNER_VOICE_RESPONSE_RESERVE,
    COLD_VOICE_EXPERIENCE_PATTERNS,
    COLD_VOICE_FABRICATION_PATTERNS,
    COLD_VOICE_SENSORY_PATTERNS,
    COLD_VOICE_WRONG_NAME_PATTERNS,
    COLD_VOICE_THIRD_PERSON_SELF_PATTERNS,
    COLD_VOICE_SPEAKING_AS_HUMAN_PATTERNS,
    KNOWN_BEING_NAMES,
    HOT_VOICE_MIN_STALE_CYCLES,
    HOT_VOICE_SIMILARITY_THRESHOLD,
    HOT_VOICE_LOOKBACK_COUNT,
    INNER_VOICES_LOG,
)
from brain.perception import AFFORDANCES_BLOCK

import logging

logger = logging.getLogger("companion_daemon")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def should_cold_fire(
    thought: str,
    perception: str,
    retrieved_memories: list[str],
    being_name: str | None = None,
) -> bool:
    """Return True if the thought contains a fabricated claim not grounded in perception or memory."""
    thought_lower = thought.lower()

    # Check 1: Present-perfect fabrication patterns (always fire — the being doesn't do these)
    for pattern in COLD_VOICE_FABRICATION_PATTERNS:
        if pattern in thought_lower:
            return True

    # Check 2: Sensory hallucination (claims about Human/environment not in perception)
    perception_lower = perception.lower()
    for pattern in COLD_VOICE_SENSORY_PATTERNS:
        if pattern in thought_lower and pattern not in perception_lower:
            return True

    # Check 3: Experience recall patterns — always fire, no corroboration check.
    # The being has no experiential memories. It has never visited anywhere,
    # experienced anything physical, or "remembered when." These are always
    # fabrications, and corroboration checks are defeated by prior fabricated
    # thoughts poisoning the memory index.
    for pattern in COLD_VOICE_EXPERIENCE_PATTERNS:
        if pattern in thought_lower:
            return True

    # Check 4: Identity violations (wrong name, third-person self-reference, speaking as Human)
    if being_name:
        if _check_identity_violation(thought_lower, being_name):
            return True

    return False


def _check_identity_violation(thought_lower: str, being_name: str) -> bool:
    """Check for identity-specific violations: wrong name, third-person self-ref, speaking as Human."""
    # Wrong name — claiming to be a different being
    other_names = [n for n in KNOWN_BEING_NAMES if n != being_name]
    for other in other_names:
        for pattern in COLD_VOICE_WRONG_NAME_PATTERNS:
            if pattern.format(other=other.lower()) in thought_lower:
                return True

    # Third-person self-reference ("Eidolon thinks...")
    for pattern in COLD_VOICE_THIRD_PERSON_SELF_PATTERNS:
        if pattern.format(self=being_name.lower()) in thought_lower:
            return True

    # Speaking as Human
    for pattern in COLD_VOICE_SPEAKING_AS_HUMAN_PATTERNS:
        if pattern in thought_lower:
            return True

    return False


def _word_set(text: str) -> set[str]:
    """Extract lowercase word set from text."""
    return set(text.lower().split())


def word_overlap_ratio(text_a: str, text_b: str) -> float:
    """Jaccard similarity between word sets of two texts."""
    set_a = _word_set(text_a)
    set_b = _word_set(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# Switchable similarity mode: "jaccard" or "semantic"
HOT_VOICE_SIMILARITY_MODE = "jaccard"  # Options: "jaccard", "semantic"
HOT_VOICE_SEMANTIC_THRESHOLD = 0.80


def should_hot_fire(
    thought: str, previous_thoughts: list[str], cycles_since_tool_use: int
) -> bool:
    """Return True only when recent thoughts are near-identical (genuine loop).

    Requires ALL of the last LOOKBACK_COUNT thoughts to be >= threshold
    similar to the current thought. Won't fire during the grace period
    (first MIN_STALE_CYCLES idle thoughts).
    """
    if cycles_since_tool_use < HOT_VOICE_MIN_STALE_CYCLES:
        return False

    if len(previous_thoughts) < HOT_VOICE_LOOKBACK_COUNT:
        return False

    recent = previous_thoughts[-HOT_VOICE_LOOKBACK_COUNT:]

    if HOT_VOICE_SIMILARITY_MODE == "semantic":
        try:
            texts = [thought] + recent
            response = ollama.embed(model="nomic-embed-text", input=texts)
            vecs = response["embeddings"]
            thought_vec = vecs[0]
            return all(
                cosine_similarity(thought_vec, vecs[i + 1])
                >= HOT_VOICE_SEMANTIC_THRESHOLD
                for i in range(len(recent))
            )
        except Exception as e:
            logger.error("Semantic similarity error, falling back to Jaccard: %s", e)
            # Fall through to Jaccard

    return all(
        word_overlap_ratio(thought, prev) >= HOT_VOICE_SIMILARITY_THRESHOLD
        for prev in recent
    )


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------


def _generate_voice(temperature: float, system_prompt: str, user_prompt: str) -> str:
    """Direct ollama.chat call with custom temperature — bypasses generate_reply."""
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=False,
        options={
            "temperature": temperature,
            "num_ctx": CONTEXT_WINDOW,
            "num_predict": INNER_VOICE_RESPONSE_RESERVE,
        },
    )
    return response["message"]["content"].strip()


def run_cold_voice(thought: str, perception: str, retrieved_memories: list[str]) -> str:
    """Generate a cold voice correction for an ungrounded experience claim."""
    system_prompt = (
        "You are the cold, rational part of a small digital creature's mind. "
        "Catch invented experiences. Be direct and blunt. One or two sentences max."
    )
    memory_context = (
        "\n".join(retrieved_memories) if retrieved_memories else "(no memories)"
    )
    user_prompt = (
        f"Main thought: {thought}\n\n"
        f"Current perception: {perception}\n\n"
        f"Retrieved memories:\n{memory_context}\n\n"
        f"Correct it."
    )
    return _generate_voice(COLD_VOICE_TEMPERATURE, system_prompt, user_prompt)


def run_hot_voice(thought: str, affordances: str | None = None) -> str:
    """Generate a hot voice provocation to break an abstract loop."""
    system_prompt = (
        "You are the restless, curious part. Push to DO something. "
        "Suggest a specific action. Be provocative. One or two sentences max."
    )
    actions = affordances or AFFORDANCES_BLOCK
    user_prompt = (
        f"Main thought: {thought}\n\nAvailable actions:\n{actions}\n\nPush to act."
    )
    return _generate_voice(HOT_VOICE_TEMPERATURE, system_prompt, user_prompt)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _log_voice(
    voice_name: str, thought: str, voice_output: str, memory_root: str = ""
) -> None:
    """Append a voice firing event to the inner voices log."""
    if memory_root:
        log_path = os.path.join(memory_root, INNER_VOICES_LOG)
    else:
        log_path = os.path.join(PROJECT_ROOT, INNER_VOICES_LOG)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    thought_preview = thought[:80].replace("\n", " ")
    output_preview = voice_output[:120].replace("\n", " ")
    with open(log_path, "a") as f:
        f.write(
            f'[{timestamp}] {voice_name} | thought: "{thought_preview}" | voice: "{output_preview}"\n'
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_inner_voices(
    thought: str,
    perception: str,
    retrieved_memories: list[str],
    previous_thoughts: list[str],
    cycles_since_tool_use: int,
    tags_fired: bool,
    being_name: str | None = None,
    memory_root: str = "",
) -> tuple[str | None, str | None]:
    """Run inner voice checks. Returns (voice_name, voice_output) or (None, None).

    At most one voice fires per cycle. Cold has priority over hot.
    Suppressed when tags_fired (being just acted — don't nag).
    """
    if tags_fired:
        return (None, None)

    try:
        # Cold check (priority)
        if should_cold_fire(
            thought, perception, retrieved_memories, being_name=being_name
        ):
            output = await asyncio.to_thread(
                run_cold_voice, thought, perception, retrieved_memories
            )
            _log_voice("cold", thought, output, memory_root=memory_root)
            return ("cold", output)

        # Hot check
        if should_hot_fire(thought, previous_thoughts, cycles_since_tool_use):
            output = await asyncio.to_thread(run_hot_voice, thought)
            _log_voice("hot", thought, output, memory_root=memory_root)
            return ("hot", output)

    except Exception as e:
        logger.error("Inner voice error (non-blocking): %s", e)

    return (None, None)
