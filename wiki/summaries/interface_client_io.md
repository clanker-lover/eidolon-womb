# interface/client_io.py

Client I/O pipeline -- generate_reply and process_message extracted from the daemon.

## What It Does

Contains the extracted `generate_reply()` and `process_message()` async functions. These are the full turn pipeline used when a human chats with the being via the socket connection.

## Key Functions

- **`generate_reply(daemon, messages, num_predict)`** -- Wraps `ollama.chat()` with daemon's active model, temperature, and context window. (Source: `interface/client_io.py:37-55`)
- **`process_message(daemon, user_input)`** -- Full 11-step turn pipeline for chat: perception, retrieval, context assembly, generation, action resolution, Layer 1 reflexes, Layer 2 heuristics, cold voice check, hot voice check (semantic similarity via embeddings), history append, turn save, fact extraction, memory rebuild. (Source: `interface/client_io.py:58-230`)

## Design

This is a parallel implementation to the process_message method on `EidolonDaemon` in `womb.py`. Both exist because the module was extracted but the daemon class still has its own copy. The daemon's `womb.py` version is used at runtime; this module exists as the cleanly-extracted version.

## Dependencies

`ollama`, `core.config`, `brain.*`, `core.stats`, `inner_voices`

See also: [womb_py](womb_py.md), [brain_cycle](brain_cycle.md)
