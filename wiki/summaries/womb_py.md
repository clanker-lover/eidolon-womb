# womb.py

Entry point and central class for the Eidolon daemon.

## What It Does

Defines `EidolonDaemon`, the top-level class that owns all runtime state and orchestrates the being's lifecycle. When run directly (`python3 womb.py`), it starts the daemon via `asyncio.run(daemon.run())`.

## Public API

- **`EidolonDaemon`** -- Main class. Holds identity, personality, memory index, fatigue, session state, idle loop, thread store, notification queue, and all connection tracking.
- **`EidolonDaemon.run()`** -- Delegates to `daemon/lifecycle.py:run()` for startup, server binding, and shutdown.
- **`EidolonDaemon.process_message(user_input)`** -- Full turn pipeline: perception, retrieval, generation, action resolution, inner voices, memory extraction. (Source: `womb.py:277-445`)
- **`EidolonDaemon.generate_reply(messages)`** -- Wraps `ollama.chat()` with configured temperature, context window, and prediction budget. (Source: `womb.py:257-271`)
- **`EidolonDaemon.load_brain(memory_root)`** -- Delegates to `daemon/lifecycle.py` to load identity, personality, facts, and memory index.

## Key Design Decisions

- **Delegation pattern**: Most methods delegate to extracted modules (`daemon/lifecycle.py`, `daemon/server.py`, `brain/cycle.py`, `brain/sleep.py`, `interface/threads_handler.py`) via lazy imports. This keeps the class as a facade. (Source: `womb.py:189-830`)
- **State persistence**: `_STATE_KEYS` tuple lists ~22 fields persisted to `~/.companion/being_state.json` via JSON serialization. Snapshot loop saves every 5 minutes. (Source: `womb.py:612-690`)
- **Single-being architecture**: Registry and scheduler fields exist but are set to `None`. The womb is a single-being public fork of a multi-being colony system. (Source: `womb.py:167-168`, `CLAUDE.md:43`)

## Dependencies

`asyncio`, `ollama`, `config` (re-export of `core.config`), `brain.*`, `core.*`, `interface.*`, `inner_voices`, `presence`, `tools`

## Architectural Role

Central nervous system. All other modules are organs called by or registered into `EidolonDaemon`. The daemon owns the event loop, the idle thought cycle, the client connection, and all state.

See also: [daemon_lifecycle](daemon_lifecycle.md), [daemon_server](daemon_server.md), [concept: daemon-architecture](../concepts/daemon_architecture.md)
