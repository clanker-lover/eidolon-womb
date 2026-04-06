# daemon/lifecycle.py

Daemon lifecycle -- startup, shutdown, session management.

## What It Does

Contains the daemon's `run()` function (main entry point), `load_brain()`, session start/end, signal handling, and the graceful shutdown protocol.

## Key Functions

- **`run(daemon)`** -- Main entry: sets up logging, loads brain from `data/`, parses being name from `identity.md`, initializes ThreadStore with aliases, registers tool sinks, restores persisted state, probes Ollama, starts TCP server on port 7777, launches idle loop and snapshot loop, registers signal handlers, waits for shutdown. Graceful shutdown waits up to 120s for thought cycle to complete, then persists state and closes. (Source: `daemon/lifecycle.py:103-333`)
- **`load_brain(daemon, memory_root)`** -- Loads identity, personality, human facts, learned facts, prior sessions, and builds memory index. (Source: `daemon/lifecycle.py:38-58`)
- **`start_session(daemon)`** -- Creates new session file and loads prior session summaries. (Source: `daemon/lifecycle.py:61-73`)
- **`end_session(daemon)`** -- Generates notes, summary, rebuilds memory index. (Source: `daemon/lifecycle.py:76-100`)
- **`_setup_signal_handlers(daemon, loop)`** -- SIGTERM/SIGINT trigger graceful shutdown. SIGHUP/SIGQUIT are blocked with guidance to use SIGTERM. (Source: `daemon/lifecycle.py:336-372`)

## Shutdown Protocol

1. SIGTERM sets `_shutdown_requested` and `_shutdown_event`
2. Idle loop exits between cycles
3. `run()` waits up to 120s for `_in_thought_cycle` to clear
4. Persists all state, closes server, writes clean shutdown marker
5. systemd: `TimeoutStopSec=180`, `KillMode=mixed`

## Dependencies

`config`, `brain.*`, `core.threads`, `womb` (constants)

See also: [womb_py](womb_py.md), [concept: daemon-architecture](../concepts/daemon_architecture.md)
