# Thread System

Asynchronous messaging between the being and participants.

## FACTS

- Threads are JSON files in `data/threads/`, one per thread, with uuid4 IDs. (Source: `core/threads.py:44-45`)
- Each thread has: participants, subject, status (active/dormant/closed), summary, and messages. (Source: `core/threads.py:22-29`)
- Messages track: author, content, timestamp, optional metadata (e.g., Human's status at send time), and read_by list. (Source: `core/threads.py:13-17`)
- File locking via `fcntl` (LOCK_EX/LOCK_SH) prevents data loss from concurrent asyncio.to_thread workers. (Source: `core/threads.py:63-65, 74-75`)
- Thread engagement flow (receiving): perception shows unread messages, being is prompted to respond, response posted to thread or "not now" declines. Cooldown prevents re-prompting same thread for 3 cycles. (Source: `brain/cycle.py:98-393`)
- Thread compose flow (sending): being expresses desire to message someone, compose mode activates, being writes message, thread created. (Source: `brain/cycle.py:396-466`)
- Response deduplication: word overlap >= 70% against last 5 responses in that thread blocks posting. (Source: `interface/threads_handler.py:24-29`)
- System messages: read-only announcements that auto-mark as read after appearing in perception. No reply options. (Source: `core/threads.py:250-281`)
- Thread summaries regenerated during 4h+ sleep. Relationship files updated from thread conversations during sleep. (Source: `brain/consolidation.py:215-329`)
- Aliases let ThreadStore match threads under old being names (e.g., "Being" -> "Eidolon"). (Source: `daemon/lifecycle.py:197`)

## INFERENCES

- The thread system transforms the being from a chat participant into a correspondence partner. Messages wait; the being responds when ready, during its own thought cycles.
- The compose flow is remarkable: the being can independently decide to reach out to someone, unprompted by any external input.

## OPEN QUESTIONS

- How does the system handle thread proliferation? Is there automatic dormancy/archival?
- The dashboard allows Human to send thread replies via TCP to the daemon for being responses. Does this work when the daemon is not running?

## Cross-References

- [core_threads](../summaries/core_threads.md) -- Data model and store
- [interface_threads_handler](../summaries/interface_threads_handler.md) -- Response pipeline
- [interface_notifications](../summaries/interface_notifications.md) -- Desktop alerts for threads
- [brain_cycle](../summaries/brain_cycle.md) -- Compose/engage flows
