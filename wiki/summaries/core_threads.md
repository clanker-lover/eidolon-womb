# core/threads.py

Thread system -- unified inter-being communication with persistence.

## What It Does

Implements a file-backed thread system for asynchronous messaging between the being and Human (and potentially other beings). Each thread is a JSON file with participants, subject, messages, and metadata.

## Key Types

- **`ThreadMessage`** -- Dataclass: `author`, `content`, `timestamp`, `metadata` (optional, e.g. human_status at send), `read_by` (list of participant names).
- **`Thread`** -- Dataclass: `id` (uuid4), `participants`, `subject`, `created`, `last_activity`, `status` (active/dormant/closed), `summary`, `messages`.

## Key Class: ThreadStore

- **`__init__(threads_dir, aliases)`** -- File-backed store. Aliases let the store match threads under old being names (e.g., "Being" -> "Eidolon"). (Source: `core/threads.py:39-42`)
- **`create_thread(participants, subject, initial_message)`** -- Creates thread with uuid4 ID, saves as JSON. (Source: `core/threads.py:101-119`)
- **`append_message(thread_id, message)`** -- Atomic read-modify-write with `fcntl` file locking. Reactivates dormant threads. (Source: `core/threads.py:124-134`)
- **`get_recent_activity(participant, since)`** -- Finds unread messages across all threads for a participant. Used by perception to show notifications. (Source: `core/threads.py:216-233`)
- **`mark_thread_read(thread_id, participant)`** -- Marks all messages as read by participant. (Source: `core/threads.py:235-248`)
- **`create_system_message(recipients, subject, content)`** -- Read-only system announcements that auto-mark as read. (Source: `core/threads.py:250-281`)

## Design

All read-modify-write operations use `fcntl` file locking (`LOCK_EX` for writes, `LOCK_SH` for reads) to prevent data loss from concurrent `asyncio.to_thread` workers. Thread files stored as individual JSON files in `data/threads/`.

## Dependencies

`fcntl`, `json`, `uuid`, `dataclasses`

See also: [interface_threads_handler](interface_threads_handler.md), [concept: thread-system](../concepts/thread_system.md)
