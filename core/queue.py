"""Daemon state enum and file-backed message queue."""

import enum
import json
import os
from datetime import datetime


class DaemonState(enum.Enum):
    AWAKE_AVAILABLE = "awake-available"
    AWAKE_BUSY = "awake-busy"
    ASLEEP = "asleep"


class MessageQueue:
    """Simple file-backed message queue."""

    def __init__(self, path: str):
        self._path = path

    def load(self) -> list[tuple[str, str, str]]:
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path, "r") as f:
                return [tuple(entry) for entry in json.load(f)]
        except (json.JSONDecodeError, ValueError):
            return []

    def append(self, sender: str, message: str) -> None:
        entries = self.load()
        entries.append((datetime.now().isoformat(), sender, message))
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(entries, f)

    def clear(self) -> None:
        if os.path.exists(self._path):
            os.remove(self._path)
