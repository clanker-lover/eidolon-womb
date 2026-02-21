import os
import sys


def load_file(filepath: str) -> str:
    try:
        with open(filepath, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: {filepath} not found", file=sys.stderr)
        return ""


def load_identity(memory_root: str) -> str:
    from config import IDENTITY_FILE

    return load_file(os.path.join(memory_root, IDENTITY_FILE))


def load_personality(memory_root: str) -> str:
    from config import PERSONALITY_FILE

    return load_file(os.path.join(memory_root, PERSONALITY_FILE))


def load_human_facts(memory_root: str) -> list[str]:
    from config import HUMAN_FILE

    text = load_file(os.path.join(memory_root, HUMAN_FILE))
    if not text:
        return []
    return [line.strip() for line in text.split("\n") if line.strip()]
