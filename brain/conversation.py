import os
from datetime import datetime


def create_session_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def init_session(project_root: str, conversations_dir: str) -> tuple[str, str]:
    session_id = create_session_id()
    full_dir = os.path.join(project_root, conversations_dir)
    os.makedirs(full_dir, exist_ok=True)
    filepath = os.path.join(full_dir, f"{session_id}.md")
    with open(filepath, "w") as f:
        f.write(f"# Session {session_id}\n\n")
    return session_id, filepath


def save_turn(filepath: str, user_msg: str, reply: str) -> None:
    with open(filepath, "a") as f:
        f.write(f"**You:** {user_msg}\n\n")
        f.write(f"**Eidolon:** {reply}\n\n")


def load_prior_sessions(
    project_root: str, conversations_dir: str, max_sessions: int = 3
) -> list[str]:
    full_dir = os.path.join(project_root, conversations_dir)
    os.makedirs(full_dir, exist_ok=True)

    files = sorted(
        [
            f
            for f in os.listdir(full_dir)
            if f.endswith(".md")
            and not f.endswith("_summary.md")
            and not f.endswith("_notes.md")
        ],
        reverse=True,
    )

    # Skip the first file — it's the current session (just created)
    prior_files = files[1 : 1 + max_sessions]

    sessions = []
    for fname in reversed(prior_files):  # oldest first
        session_id = fname.replace(".md", "")
        summary_path = os.path.join(full_dir, f"{session_id}_summary.md")
        if os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                text = f.read().strip()
        else:
            path = os.path.join(full_dir, fname)
            with open(path, "r") as f:
                text = f.read().strip()
        if text:
            sessions.append(f"[Session {session_id}]\n{text}")

    return sessions
