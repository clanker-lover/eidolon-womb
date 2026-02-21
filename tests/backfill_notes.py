"""Generate Eidolon notes for all existing session transcripts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import MODEL_NAME, CONTEXT_WINDOW
from brain.memory import generate_eidolon_notes

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
CONVERSATIONS_DIR = os.path.join(PROJECT_ROOT, "data", "conversations")


def main():
    files = sorted(
        f
        for f in os.listdir(CONVERSATIONS_DIR)
        if f.endswith(".md")
        and not f.endswith("_summary.md")
        and not f.endswith("_notes.md")
    )
    print(f"Found {len(files)} session files\n")

    for fname in files:
        filepath = os.path.join(CONVERSATIONS_DIR, fname)
        session_id = fname.replace(".md", "")
        notes_path = filepath.replace(".md", "_notes.md")

        print(f"--- {session_id} ---")

        if os.path.exists(notes_path):
            print("(skipped — notes already exist)")
            print()
            continue

        notes = generate_eidolon_notes(filepath, MODEL_NAME, CONTEXT_WINDOW, PROJECT_ROOT)
        if notes:
            print(notes)
        else:
            print("(skipped — empty or too short)")
        print()


if __name__ == "__main__":
    main()
