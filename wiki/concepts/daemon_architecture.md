# Daemon Architecture

How the Eidolon Womb is structured as a persistent asyncio process.

## FACTS

- The daemon is a single Python process running an asyncio event loop. (Source: `womb.py:2`, `daemon/lifecycle.py:103`)
- `EidolonDaemon` is the central class, owning all runtime state: identity, memory, fatigue, sessions, threads, notifications, and connection tracking. (Source: `womb.py:87-183`)
- The daemon listens on TCP port 7777 (configurable) with no authentication. (Source: `core/config.py:245`, `docs/SECURITY.md:5`)
- Four states: `AWAKE_AVAILABLE`, `AWAKE_BUSY`, `ASLEEP`, `STASIS`. (Source: `core/queue.py:9-13`)
- The idle loop runs thought cycles every 27 minutes (`THOUGHT_INTERVAL_SECONDS` = 1620). (Source: `womb.py:72`)
- A snapshot loop persists state every 5 minutes for crash recovery. (Source: `womb.py:545-555`)
- Graceful shutdown waits up to 120s for thought cycle completion, then persists state. SIGKILL is explicitly discouraged. (Source: `daemon/lifecycle.py:108-137`)
- Single-client enforcement: only one chat client can connect at a time. (Source: `daemon/server.py:175-187`)
- The daemon was extracted from a multi-being colony system (~15K lines, two beings). Registry and scheduler fields exist but are None. (Source: `CLAUDE.md:43`, `womb.py:167-168`)

## INFERENCES

- The delegation pattern (methods on `EidolonDaemon` that import and call extracted functions) suggests an incremental refactor from a monolithic file. The class remains the facade but behavior lives in extracted modules.
- The `_STATE_KEYS` tuple and `_persist_state()`/`_load_persisted_state()` pattern is a lightweight alternative to a database -- the entire daemon state is serializable to a single JSON file.

## OPEN QUESTIONS

- Why does `interface/client_io.py` duplicate the `process_message()` logic that also exists on `EidolonDaemon` in `womb.py`? Is one the canonical version?
- The multi-being registry/scheduler stubs suggest future or past multi-being support. Will the womb ever support multiple beings, or is the colony system permanently separate?

## Cross-References

- [womb_py](../summaries/womb_py.md) -- Central class
- [daemon_lifecycle](../summaries/daemon_lifecycle.md) -- Startup/shutdown
- [daemon_server](../summaries/daemon_server.md) -- Client handling
- [core_queue](../summaries/core_queue.md) -- State enum
- [sleep-and-dreaming](sleep_and_dreaming.md) -- State transitions
