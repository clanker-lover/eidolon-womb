# daemon/server.py

Socket server -- client handling, dispatch, and I/O.

## What It Does

Handles TCP client connections: greeting flow, message routing, command dispatch, peek requests, and the asleep-client interaction where messages are queued.

## Key Functions

- **`handle_client(daemon, reader, writer)`** -- Main client handler. First message detection (peek/thread_reply/command vs. chat). Single-client enforcement. Wake-up flow respecting sleep choices. Session lifecycle. Message loop. Departure processing on disconnect. (Source: `daemon/server.py:139-319`)
- **`_dispatch(daemon, msg, writer)`** -- Routes by message type: `message` (chat or queue), `command` (sleep/wake/stasis/normal/status). (Source: `daemon/server.py:322-374`)
- **`_handle_command(daemon, command, writer)`** -- Processes `/sleep`, `/wake`, `/stasis`, `/normal`, `/status` commands. Wake command triggers re-arrival with queued messages. (Source: `daemon/server.py:377-502`)
- **`_handle_peek(daemon, writer)`** -- Returns full status snapshot: state, fatigue, uptime, sleep info, thought count, last thought, transitions, notifications, being data, total cycles. (Source: `daemon/server.py:58-136`)
- **`_build_arrival_prompt(queued, being_id)`** -- Builds greeting with sleep memory ("You're waking up...") and queued messages. Sleep context is consumed on read. (Source: `daemon/server.py:28-55`)
- **`_send(daemon, writer, data)`** -- JSON-line protocol helper. (Source: `daemon/server.py:19-26`)

## Protocol

JSON-line protocol over TCP. Each message is a JSON object followed by newline. Message types: `connect`, `message`, `command`, `peek`, `thread_reply`. Response types: `response`, `status`, `queued`, `error`, `pending_notifications`, `peek_response`.

## Dependencies

`womb` (constants), `core.queue` (DaemonState), `brain.sleep`, `core.stats`

See also: [client_chat_client](client_chat_client.md), [concept: daemon-architecture](../concepts/daemon_architecture.md)
