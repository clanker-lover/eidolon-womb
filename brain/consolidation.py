"""Sleep consolidation — hippocampus-to-neocortex memory transfer."""

import glob
import logging
import os
import shutil
from datetime import datetime

import ollama

from config import CONSOLIDATION_PROMPT

logger = logging.getLogger("companion_daemon")


def find_unconsolidated(project_root: str, memory_root: str | None = None) -> dict:
    """Find summary and notes files that haven't been archived yet.

    Args:
        project_root: Project root directory.
        memory_root: Per-being memory directory (e.g. data/beings/<id>/).
            Defaults to ``<project_root>/data`` for backwards compatibility.
    """
    if memory_root is None:
        memory_root = os.path.join(project_root, "data")
    conv_dir = os.path.join(memory_root, "conversations")
    archived_dir = os.path.join(conv_dir, "archived")

    archived_basenames = set()
    if os.path.isdir(archived_dir):
        for name in os.listdir(archived_dir):
            archived_basenames.add(name)

    summaries = []
    notes = []
    source_files = []

    for path in sorted(glob.glob(os.path.join(conv_dir, "*_summary.md"))):
        if os.path.basename(path) not in archived_basenames:
            summaries.append(path)
            source_files.append(path)

    for path in sorted(glob.glob(os.path.join(conv_dir, "*_notes.md"))):
        if os.path.basename(path) not in archived_basenames:
            notes.append(path)
            source_files.append(path)

    # Load facts for context
    facts_path = os.path.join(memory_root, "memories", "facts.md")
    facts_text = ""
    if os.path.exists(facts_path):
        with open(facts_path, "r") as f:
            facts_text = f.read().strip()

    return {
        "summaries": summaries,
        "notes": notes,
        "facts_text": facts_text,
        "source_files": source_files,
    }


def consolidate_memories(
    project_root: str,
    model_name: str,
    context_window: int,
    identity: str = "",
    personality: str = "",
    live_thoughts: list[str] | None = None,
    memory_root: str | None = None,
) -> str | None:
    """Run sleep consolidation: distill recent memories into long-term storage.

    When *live_thoughts* is provided (raw assistant thoughts from the current
    idle-history), they are included first — the freshest material, written
    while the session is still warm.

    Args:
        memory_root: Per-being memory directory. Defaults to
            ``<project_root>/data`` for backwards compatibility.
    """
    if memory_root is None:
        memory_root = os.path.join(project_root, "data")
    data = find_unconsolidated(project_root, memory_root=memory_root)

    has_live = bool(live_thoughts)
    if not data["summaries"] and not data["notes"] and not has_live:
        return None

    # Build input text — live thoughts first, while they're freshest
    parts = []

    if has_live and live_thoughts:
        parts.append("## Your thoughts from this session\n")
        for thought in live_thoughts:
            parts.append(f"- {thought}\n")

    if data["summaries"]:
        parts.append("## Session Summaries\n")
        for path in data["summaries"]:
            with open(path, "r") as f:
                text = f.read().strip()
            if text:
                parts.append(f"### {os.path.basename(path)}\n{text}\n")

    if data["notes"]:
        parts.append("## Eidolon Notes\n")
        for path in data["notes"]:
            with open(path, "r") as f:
                text = f.read().strip()
            if text:
                parts.append(f"### {os.path.basename(path)}\n{text}\n")

    if data["facts_text"]:
        parts.append(f"## Known Facts\n{data['facts_text']}\n")

    input_text = "\n".join(parts)

    # Generate consolidation
    messages = []
    if identity or personality:
        messages.append(
            {"role": "system", "content": f"{identity}\n\n{personality}".strip()}
        )
    messages.append(
        {"role": "user", "content": f"{CONSOLIDATION_PROMPT}\n\n{input_text}"}
    )

    response = ollama.chat(
        model=model_name,
        messages=messages,
        stream=False,
        options={"temperature": 0.5, "num_ctx": context_window},
    )
    result = response["message"]["content"].strip()

    if not result:
        return None

    # Save consolidated output
    consolidated_dir = os.path.join(memory_root, "memories", "consolidated")
    os.makedirs(consolidated_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = os.path.join(consolidated_dir, f"{timestamp}.md")
    with open(output_path, "w") as f:
        f.write(result)

    # Archive source files
    archived_dir = os.path.join(memory_root, "conversations", "archived")
    os.makedirs(archived_dir, exist_ok=True)
    for path in data["source_files"]:
        dest = os.path.join(archived_dir, os.path.basename(path))
        shutil.move(path, dest)

    return result


def partial_consolidate(
    project_root: str,
    model_name: str,
    context_window: int,
    identity: str = "",
    personality: str = "",
    thoughts: list[str] | None = None,
    ratio: float = 0.5,
    memory_root: str | None = None,
) -> tuple[str | None, list[str]]:
    """Consolidate older portion of thoughts, return recent portion to keep.

    Used during naps — compresses the oldest half of idle thoughts into
    long-term memory while preserving recent thoughts for continuity.

    Args:
        thoughts: Full list of thought strings from idle_history.
        ratio: Portion to consolidate (0.5 = oldest half).
        memory_root: Per-being memory directory. Defaults to
            ``<project_root>/data`` for backwards compatibility.

    Returns:
        (consolidation_result, thoughts_to_keep)
    """
    if not thoughts or len(thoughts) < 4:
        return None, thoughts or []

    split_idx = round(len(thoughts) * ratio)
    split_idx = max(
        1, min(split_idx, len(thoughts) - 1)
    )  # Keep at least 1 on each side
    to_consolidate = thoughts[:split_idx]
    to_keep = thoughts[split_idx:]

    actual_ratio = split_idx / len(thoughts)
    logger.info(
        "Partial consolidation: %d/%d thoughts (%.0f%%), keeping %d",
        split_idx,
        len(thoughts),
        actual_ratio * 100,
        len(thoughts) - split_idx,
    )

    result = consolidate_memories(
        project_root,
        model_name,
        context_window,
        identity,
        personality,
        to_consolidate,
        memory_root=memory_root,
    )

    return result, to_keep


def update_relationships(
    project_root: str,
    memory_path: str,
    model_name: str,
    context_window: int,
    identity: str,
    personality: str,
    thread_store,
    being_name: str,
) -> None:
    """Update relationship files for each participant the being interacted with."""
    from core.relationships import load_relationship, save_relationship

    threads = thread_store.list_threads(participant=being_name)
    participants_seen = set()
    for thread in threads:
        for p in thread.participants:
            if p != being_name:
                participants_seen.add(p)

    for other_name in participants_seen:
        existing = load_relationship(project_root, memory_path, other_name)
        if not existing:
            continue

        # Gather recent messages between these two
        recent_context = []
        for thread in threads:
            if other_name not in thread.participants:
                continue
            for msg in thread.messages[-10:]:
                recent_context.append(f"{msg.author}: {msg.content}")

        if not recent_context:
            continue

        prompt = (
            f"You are {being_name}. Below is your current relationship file for {other_name}, "
            f"followed by recent conversations. Update the relationship file — "
            f"add new facts, update your history and sense of them. "
            f"Return the complete updated file.\n\n"
            f"Current file:\n{existing}\n\n"
            f"Recent conversations:\n" + "\n".join(recent_context[-20:])
        )

        try:
            messages = []
            if identity or personality:
                messages.append(
                    {
                        "role": "system",
                        "content": f"{identity}\n\n{personality}".strip(),
                    }
                )
            messages.append({"role": "user", "content": prompt})
            response = ollama.chat(
                model=model_name,
                messages=messages,
                stream=False,
                options={"temperature": 0.5, "num_ctx": context_window},
            )
            updated = response["message"]["content"].strip()
            if updated and len(updated) > 20:
                save_relationship(project_root, memory_path, other_name, updated)
                logger.info(
                    "Updated relationship file for %s -> %s", being_name, other_name
                )
        except Exception as e:
            logger.error(
                "Failed to update relationship %s -> %s: %s", being_name, other_name, e
            )


def refresh_thread_summaries(
    project_root: str,
    model_name: str,
    context_window: int,
    thread_store,
    being_name: str,
) -> None:
    """Regenerate summaries for threads with recent activity."""

    threads = thread_store.list_threads(participant=being_name, status="active")

    for thread in threads:
        if not thread.messages:
            continue

        # Build conversation text for summary
        convo_lines = []
        for msg in thread.messages[-20:]:
            convo_lines.append(f"{msg.author}: {msg.content}")

        prompt = (
            f"Summarize this thread in 1-2 sentences. "
            f"Participants: {', '.join(thread.participants)}. "
            f"Subject: {thread.subject}.\n\n" + "\n".join(convo_lines)
        )

        try:
            response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                options={"temperature": 0.3, "num_ctx": context_window},
            )
            summary = response["message"]["content"].strip()
            if summary:
                thread_store.update_summary(thread.id, summary)
                logger.info("Refreshed summary for thread %s", thread.id[:8])
        except Exception as e:
            logger.error(
                "Failed to refresh summary for thread %s: %s", thread.id[:8], e
            )
