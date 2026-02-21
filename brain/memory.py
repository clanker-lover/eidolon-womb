import os
import sys
from datetime import datetime

import re

import ollama


def _is_none_response(text: str) -> bool:
    """Check if the text is a NONE response, tolerating punctuation and whitespace."""
    return bool(re.match(r"^none[.!]?$", text.strip(), re.IGNORECASE))


def _is_junk_line(line: str) -> bool:
    """Filter out model commentary that isn't a fact."""
    if _is_none_response(line):
        return True
    lower = line.lower()
    if lower.startswith("note:") or lower.startswith("note that"):
        return True
    if lower.startswith("there are no") or lower.startswith("there is no"):
        return True
    if lower.startswith("no personal") or lower.startswith("i could not"):
        return True
    return False


def summarize_session(
    session_filepath: str,
    model_name: str,
    context_window: int,
) -> str | None:
    from config import SESSION_SUMMARY_PROMPT

    try:
        with open(session_filepath, "r") as f:
            transcript = f.read().strip()
    except FileNotFoundError:
        return None

    # Skip if transcript is empty or just the header
    lines = [ln for ln in transcript.split("\n") if ln.strip()]
    if len(lines) <= 1:
        return None

    prompt = f"{SESSION_SUMMARY_PROMPT}\n\n{transcript}"
    try:
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"temperature": 0.0, "num_ctx": context_window},
        )
        summary = response["message"]["content"].strip()
    except Exception as e:
        print(f"Session summary error: {e}", file=sys.stderr)
        return None

    if not summary:
        return None

    summary_path = session_filepath.replace(".md", "_summary.md")
    with open(summary_path, "w") as f:
        f.write(summary)

    return summary


def generate_eidolon_notes(
    session_filepath: str,
    model_name: str,
    context_window: int,
    project_root: str = "",
) -> str | None:
    from config import EIDOLON_REFLECTION_PROMPT
    from brain.identity import load_identity, load_personality

    try:
        with open(session_filepath, "r") as f:
            transcript = f.read().strip()
    except FileNotFoundError:
        return None

    lines = [ln for ln in transcript.split("\n") if ln.strip()]
    if len(lines) <= 1:
        return None

    identity_text = load_identity(project_root)
    personality_text = load_personality(project_root)

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": f"{identity_text}\n\n{personality_text}"},
                {
                    "role": "user",
                    "content": f"{EIDOLON_REFLECTION_PROMPT}\n\n{transcript}",
                },
            ],
            stream=False,
            options={"temperature": 0.3, "num_ctx": context_window},
        )
        notes = response["message"]["content"].strip()
    except Exception as e:
        print(f"Eidolon notes error: {e}", file=sys.stderr)
        return None

    if not notes:
        return None

    notes_path = session_filepath.replace(".md", "_notes.md")
    with open(notes_path, "w") as f:
        f.write(notes)

    return notes


def load_learned_facts(project_root: str, memories_file: str) -> list[str]:
    path = os.path.join(project_root, memories_file)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        lines = f.read().strip().split("\n")
    return [line.strip() for line in lines if line.strip()]


def extract_facts(
    user_message: str,
    model_name: str,
    extraction_prompt: str,
    context_window: int,
) -> list[str]:
    try:
        prompt = f"{extraction_prompt}\n\nUser: {user_message}"
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"temperature": 0.0, "num_ctx": context_window},
        )
        text = response["message"]["content"].strip()
        if not text or _is_none_response(text):
            return []
        facts = []
        for line in text.split("\n"):
            line = line.strip().lstrip("-•* ")
            if line and not _is_junk_line(line):
                facts.append(line)
        return facts
    except Exception as e:
        print(f"Memory extraction error: {e}", file=sys.stderr)
        return []


def _strip_date_prefix(fact: str) -> str:
    if fact.startswith("[") and "]" in fact:
        return fact[fact.index("]") + 1 :].strip()
    return fact.strip()


def _is_duplicate(new_fact: str, existing_fact: str) -> bool:
    new_clean = _strip_date_prefix(new_fact).lower()
    existing_clean = _strip_date_prefix(existing_fact).lower()
    return new_clean in existing_clean or existing_clean in new_clean


def save_facts(
    project_root: str,
    memories_file: str,
    new_facts: list[str],
    existing_facts: list[str],
) -> list[str]:
    if not new_facts:
        return existing_facts

    path = os.path.join(project_root, memories_file)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    date_prefix = datetime.now().strftime("[%Y-%m-%d]")
    added = []
    for fact in new_facts:
        is_dup = any(_is_duplicate(fact, ef) for ef in existing_facts)
        if not is_dup:
            dated_fact = f"{date_prefix} {fact}"
            added.append(dated_fact)

    if added:
        with open(path, "a") as f:
            for fact in added:
                f.write(fact + "\n")

    return existing_facts + added
