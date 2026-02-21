"""Thread system — unified inter-being communication with persistence."""

import fcntl
import json
import os
import uuid
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime


@dataclass
class ThreadMessage:
    author: str  # Being name, "Human", or "System"
    content: str
    timestamp: str  # ISO 8601
    metadata: dict | None = None  # Optional: human_status at send time, etc.
    read_by: list[str] = field(default_factory=list)  # Participants who have seen this


@dataclass
class Thread:
    id: str  # uuid4
    participants: list[str]  # names (not IDs — Human has no being_id)
    subject: str
    created: str
    last_activity: str
    status: str  # "active" | "dormant" | "closed"
    summary: str  # auto-generated gist
    messages: list[ThreadMessage] = field(default_factory=list)


class ThreadStore:
    """Shared thread storage backed by individual JSON files in data/threads/.

    All read-modify-write operations use fcntl file locking to prevent
    data loss from concurrent access (e.g. asyncio.to_thread workers).
    """

    def __init__(self, threads_dir: str):
        self._dir = threads_dir
        os.makedirs(self._dir, exist_ok=True)

    def _thread_path(self, thread_id: str) -> str:
        return os.path.join(self._dir, f"{thread_id}.json")

    @staticmethod
    def _parse_thread(data: dict) -> Thread:
        """Parse a Thread from a dict, filtering to known fields."""
        msg_fields = {f.name for f in fields(ThreadMessage)}
        thread_fields = {f.name for f in fields(Thread)}
        messages = [
            ThreadMessage(**{k: v for k, v in m.items() if k in msg_fields})
            for m in data.pop("messages", [])
        ]
        thread_data = {k: v for k, v in data.items() if k in thread_fields}
        return Thread(**thread_data, messages=messages)

    def _save_thread(self, thread: Thread) -> None:
        data = asdict(thread)
        path = self._thread_path(thread.id)
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load_thread(self, thread_id: str) -> Thread | None:
        path = self._thread_path(thread_id)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return self._parse_thread(data)

    def _locked_update(self, thread_id: str, update_fn) -> Thread:
        """Atomic read-modify-write with exclusive file lock.

        update_fn receives the Thread and should mutate it in place.
        Returns the updated Thread.
        """
        path = self._thread_path(thread_id)
        with open(path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                data = json.load(f)
                thread = self._parse_thread(data)
                update_fn(thread)
                f.seek(0)
                f.truncate()
                json.dump(asdict(thread), f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return thread

    def create_thread(
        self,
        participants: list[str],
        subject: str,
        initial_message: ThreadMessage | None = None,
    ) -> Thread:
        now = datetime.now().isoformat()
        thread = Thread(
            id=str(uuid.uuid4()),
            participants=sorted(participants),
            subject=subject,
            created=now,
            last_activity=now,
            status="active",
            summary="",
            messages=[initial_message] if initial_message else [],
        )
        self._save_thread(thread)
        return thread

    def get_thread(self, thread_id: str) -> Thread | None:
        return self._load_thread(thread_id)

    def append_message(self, thread_id: str, message: ThreadMessage) -> Thread:
        def _append(thread: Thread):
            thread.messages.append(message)
            thread.last_activity = message.timestamp
            if thread.status == "dormant":
                thread.status = "active"

        try:
            return self._locked_update(thread_id, _append)
        except FileNotFoundError:
            raise KeyError(f"Thread '{thread_id}' not found")

    def list_threads(
        self,
        participant: str | None = None,
        status: str | None = None,
    ) -> list[Thread]:
        threads: list[Thread] = []
        if not os.path.isdir(self._dir):
            return threads
        for fname in os.listdir(self._dir):
            if not fname.endswith(".json"):
                continue
            thread_id = fname[:-5]
            thread = self._load_thread(thread_id)
            if thread is None:
                continue
            if participant and participant not in thread.participants:
                continue
            if status and thread.status != status:
                continue
            threads.append(thread)
        threads.sort(key=lambda t: t.last_activity, reverse=True)
        return threads

    def search_thread(
        self,
        thread_id: str,
        query: str,
        max_results: int = 3,
    ) -> list[ThreadMessage]:
        thread = self._load_thread(thread_id)
        if thread is None:
            return []
        query_lower = query.lower()
        matches = []
        for msg in thread.messages:
            if query_lower in msg.content.lower():
                matches.append(msg)
                if len(matches) >= max_results:
                    break
        return matches

    def update_summary(self, thread_id: str, summary: str) -> Thread:
        def _update(thread: Thread):
            thread.summary = summary

        try:
            return self._locked_update(thread_id, _update)
        except FileNotFoundError:
            raise KeyError(f"Thread '{thread_id}' not found")

    def update_status(self, thread_id: str, status: str) -> Thread:
        if status not in ("active", "dormant", "closed"):
            raise ValueError(f"Invalid thread status: {status}")

        def _update(thread: Thread):
            thread.status = status

        try:
            return self._locked_update(thread_id, _update)
        except FileNotFoundError:
            raise KeyError(f"Thread '{thread_id}' not found")

    def find_or_create_thread(
        self,
        participants: list[str],
        subject: str | None = None,
    ) -> Thread:
        sorted_participants = sorted(participants)
        for thread in self.list_threads(status="active"):
            if sorted(thread.participants) == sorted_participants:
                return thread
        return self.create_thread(
            sorted_participants,
            subject or f"Conversation: {', '.join(sorted_participants)}",
        )

    def get_recent_activity(
        self,
        participant: str,
        since: str | None = None,
    ) -> list[tuple[Thread, ThreadMessage]]:
        results = []
        for thread in self.list_threads(participant=participant):
            for msg in reversed(thread.messages):
                if msg.author == participant:
                    continue
                if since and msg.timestamp <= since:
                    break  # Older messages won't match either
                if participant in (msg.read_by or []):
                    break  # Hit a read message — everything before it is also read
                results.append((thread, msg))
        results.sort(key=lambda x: x[1].timestamp, reverse=True)
        return results

    def mark_thread_read(self, thread_id: str, participant: str) -> None:
        """Mark all messages in a thread as read by participant."""
        path = self._thread_path(thread_id)
        if not os.path.exists(path):
            return

        def _mark_read(thread: Thread):
            for msg in thread.messages:
                if msg.author != participant and participant not in (msg.read_by or []):
                    if msg.read_by is None:
                        msg.read_by = []
                    msg.read_by.append(participant)

        self._locked_update(thread_id, _mark_read)

    def create_system_message(
        self,
        recipients: list[str],
        subject: str,
        content: str,
    ) -> Thread:
        """Create a read-only system announcement thread.

        System messages appear in perception but don't trigger engagement
        prompts or reply options. They auto-mark as read after being shown.
        """
        now = datetime.now().isoformat()
        msg = ThreadMessage(
            author="System",
            content=content,
            timestamp=now,
            metadata={"system_message": True},
        )
        # Include "System" in participants so it's findable, plus all recipients
        participants = sorted(set(recipients + ["System"]))
        thread = Thread(
            id=str(uuid.uuid4()),
            participants=participants,
            subject=subject,
            created=now,
            last_activity=now,
            status="active",
            summary="System announcement",
            messages=[msg],
        )
        self._save_thread(thread)
        return thread

    def count_active(self, participant: str | None = None) -> int:
        return len(self.list_threads(participant=participant, status="active"))
