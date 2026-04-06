# client/chat.py

Standalone synchronous chat client -- no daemon required.

## What It Does

A simpler, synchronous chat client that runs the full thought pipeline locally without connecting to the daemon. Useful for testing or when the daemon is not running.

## Key Functions

- **`main()`** -- Loads identity, personality, facts, memory index. Runs interactive loop: perception, retrieval, context assembly, generation, action resolution (sync), Layer 1/2 inner voice checks. Saves turns and extracts facts on each exchange. On exit, generates session notes and summary. (Source: `client/chat.py:64-179`)
- **`generate_reply(messages)`** -- Direct synchronous `ollama.chat()` call. (Source: `client/chat.py:50-61`)

## Design

This is the original pre-daemon chat interface. It lacks the idle thought cycle, sleep system, thread system, notifications, and inner voices (cold/hot). It does include the Layer 1/2 reflex checks and action tag resolution (sync version).

## Dependencies

`ollama`, `core.config`, `brain.*`

See also: [client_chat_client](client_chat_client.md), [womb_py](womb_py.md)
