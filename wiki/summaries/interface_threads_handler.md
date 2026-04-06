# interface/threads_handler.py

Thread engagement and response handling.

## What It Does

Extracted logic for generating being responses to threads through the full thought pipeline. Handles deduplication, the engagement flow (being replies to threads), and the thread_reply protocol (Human sends via dashboard).

## Key Functions

- **`engage_thread(daemon, thread_id, user_message)`** -- Full pipeline for being's thread reply: loads relationship file, assembles thread context (12K token budget), generates reply, runs Layer 1 reflexes, hot voice similarity check against prior thread messages, Layer 2 heuristics, appends to thread, marks read. (Source: `interface/threads_handler.py:44-159`)
- **`handle_thread_reply(daemon, msg, writer)`** -- Protocol handler for dashboard thread replies. Always appends Human's message immediately. Generates being response under lock (non-blocking if busy). (Source: `interface/threads_handler.py:162-244`)
- **`is_duplicate_thread_response(daemon, thread_id, reply)`** -- Checks word overlap (>= 0.70) against last 5 responses in that thread. (Source: `interface/threads_handler.py:24-29`)
- **`record_thread_response(daemon, thread_id, reply)`** -- Records response for future dedup (keeps last 10 per thread). (Source: `interface/threads_handler.py:32-41`)

## Dependencies

`brain.perception`, `brain.context` (assemble_thread_context), `brain.inner_voice`, `core.threads`, `core.relationships`, `inner_voices`

See also: [core_threads](core_threads.md), [concept: thread-system](../concepts/thread_system.md)
