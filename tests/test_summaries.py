"""Generate summaries for all existing session transcripts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import MODEL_NAME, CONTEXT_WINDOW
from brain.memory import summarize_session

CONVERSATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "conversations")


def main():
    files = sorted(
        f
        for f in os.listdir(CONVERSATIONS_DIR)
        if f.endswith(".md") and not f.endswith("_summary.md")
    )
    print(f"Found {len(files)} session files\n")

    for fname in files:
        filepath = os.path.join(CONVERSATIONS_DIR, fname)
        session_id = fname.replace(".md", "")
        print(f"--- {session_id} ---")
        summary = summarize_session(filepath, MODEL_NAME, CONTEXT_WINDOW)
        if summary:
            print(summary)
        else:
            print("(skipped — empty or too short)")
        print()


if __name__ == "__main__":
    main()
