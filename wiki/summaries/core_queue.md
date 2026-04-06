# core/queue.py

Daemon state enum and file-backed message queue.

## What It Does

Defines the four daemon states and a simple file-backed message queue for storing messages received while the being is asleep or busy.

## Key Types

- **`DaemonState`** -- Enum with four states:
  - `AWAKE_AVAILABLE` -- Thinking, can receive messages
  - `AWAKE_BUSY` -- Mid-thought cycle, queue messages
  - `ASLEEP` -- Sleeping, messages wait for wake
  - `STASIS` -- Paused by human, no cycles run

- **`MessageQueue`** -- File-backed queue storing `(timestamp, sender, message)` tuples as JSON. Methods: `load()`, `append(sender, message)`, `clear()`. Path: `~/.companion/message_queue.json`. (Source: `core/queue.py:16-40`)

## Dependencies

`json`, `os`, `datetime`, `enum`

See also: [concept: daemon-architecture](../concepts/daemon_architecture.md), [daemon_server](daemon_server.md)
