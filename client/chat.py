import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import ollama  # noqa: E402 — must come after sys.path insert
from core.config import (  # noqa: E402
    MODEL_NAME,
    TEMPERATURE,
    CONTEXT_WINDOW,
    RESPONSE_RESERVE,
    MEMORIES_FILE,
    CONVERSATIONS_DIR,
    INNER_VOICE_LOG,
    INNER_VOICE_MAX_RETRIES,
    MEMORY_EXTRACTION_PROMPT,
    MAX_PRIOR_SESSIONS,
    RETRIEVAL_TOP_K,
)
from brain.perception import build_perception  # noqa: E402
from brain.identity import load_identity, load_personality, load_human_facts  # noqa: E402
from brain.context import assemble_messages  # noqa: E402
from brain.conversation import init_session, save_turn, load_prior_sessions  # noqa: E402
from brain.memory import (
    load_learned_facts,
    extract_facts,
    save_facts,
    summarize_session,
    generate_eidolon_notes,
)  # noqa: E402
from brain.retrieval import MemoryIndex  # noqa: E402
from brain.inner_voice import run_layer1_reflexes, run_layer2_heuristics  # noqa: E402
from brain.actions import resolve_actions_sync  # noqa: E402


def _get_memory_root() -> str:
    """Return the being's data root. Single-being womb: always data/."""
    return os.path.join(PROJECT_ROOT, "data")


def _exit_session(session_filepath, session_id):
    generate_eidolon_notes(session_filepath, MODEL_NAME, CONTEXT_WINDOW, PROJECT_ROOT)
    summary = summarize_session(session_filepath, MODEL_NAME, CONTEXT_WINDOW)
    if summary:
        print(f"\nSession summary: {summary}")
    print(f"Session saved: {session_id}")


def generate_reply(messages: list[dict]) -> str:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        stream=False,
        options={
            "temperature": TEMPERATURE,
            "num_ctx": CONTEXT_WINDOW,
            "num_predict": RESPONSE_RESERVE,
        },
    )
    return response["message"]["content"]


def main():
    from core.config import BEING_NAME

    memory_root = _get_memory_root()
    identity = load_identity(memory_root)
    personality = load_personality(memory_root)
    human_facts = load_human_facts(memory_root)
    learned_facts = load_learned_facts(memory_root, MEMORIES_FILE)
    session_summaries = load_prior_sessions(
        memory_root, CONVERSATIONS_DIR, MAX_PRIOR_SESSIONS
    )
    session_id, session_filepath = init_session(memory_root, CONVERSATIONS_DIR)

    # Parse being name from identity
    being_name = BEING_NAME
    if identity:
        for line in identity.splitlines():
            line = line.strip()
            if line.startswith("# "):
                being_name = line[2:].strip()
                break

    memory_index = MemoryIndex(memory_root)
    memory_index.rebuild()

    history: list[dict] = []
    log_file = os.path.join(memory_root, INNER_VOICE_LOG)

    print(f"{being_name} is awake.")

    while True:
        try:
            user_input = input("You: ")
        except (KeyboardInterrupt, EOFError):
            _exit_session(session_filepath, session_id)
            break

        if not user_input.strip():
            continue

        if user_input.strip().lower() in ("quit", "exit"):
            _exit_session(session_filepath, session_id)
            break

        perception = build_perception()
        retrieved = memory_index.search(user_input, top_k=RETRIEVAL_TOP_K)
        messages, _tokens_used = assemble_messages(
            perception,
            identity,
            personality,
            human_facts,
            learned_facts,
            history,
            user_input,
            session_summaries,
            retrieved_memories=retrieved,
        )

        try:
            reply = generate_reply(messages)
        except Exception as e:
            print(f"Error talking to Ollama: {e}", file=sys.stderr)
            continue

        # Action tag resolution
        try:
            reply = resolve_actions_sync(reply, generate_reply, messages)
        except Exception as e:
            print(f"Action resolution error: {e}", file=sys.stderr)

        # Layer 1: reflex checks with retry
        for _ in range(INNER_VOICE_MAX_RETRIES):
            passed, correction = run_layer1_reflexes(
                reply, perception, identity, personality
            )
            if passed:
                break
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": correction})
            try:
                reply = generate_reply(messages)
            except Exception as e:
                print(f"Error talking to Ollama: {e}", file=sys.stderr)
                break

        # Layer 2: heuristic logging (never blocks)
        run_layer2_heuristics(reply, log_file)

        print(f"{being_name}: {reply}")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

        # Save conversation turn
        try:
            save_turn(session_filepath, user_input, reply, being_name)
        except Exception as e:
            print(f"Conversation save error: {e}", file=sys.stderr)

        # Extract and save facts
        try:
            new_facts = extract_facts(
                user_input,
                MODEL_NAME,
                MEMORY_EXTRACTION_PROMPT,
                CONTEXT_WINDOW,
            )
            learned_facts = save_facts(
                memory_root, MEMORIES_FILE, new_facts, learned_facts
            )
        except Exception as e:
            print(f"Memory save error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
