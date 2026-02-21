"""Per-being statistics tracking."""

import json
from datetime import datetime
from pathlib import Path

STATS_FILE = "stats.json"


def _load_stats(root: str) -> dict:
    path = Path(root) / "data" / STATS_FILE
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_stats(root: str, stats: dict) -> None:
    path = Path(root) / "data" / STATS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2))


def increment(root: str, being_id: str, key: str, amount: int = 1) -> None:
    """Increment a counter for a being. Keys: 'thoughts', 'mail_sent', 'mail_received', 'tool_use', 'threads_created', 'thread_replies'."""
    stats = _load_stats(root)
    if being_id not in stats:
        stats[being_id] = {}
    stats[being_id][key] = stats[being_id].get(key, 0) + amount
    stats[being_id]["last_updated"] = datetime.now().isoformat()
    _save_stats(root, stats)


def get_stats(root: str, being_id: str) -> dict:
    """Get all stats for a being."""
    stats = _load_stats(root)
    return stats.get(being_id, {})


def get_all_stats(root: str) -> dict:
    """Get stats for all beings."""
    return _load_stats(root)
