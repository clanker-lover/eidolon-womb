# client/chat_client.py

Lightweight terminal client for the womb daemon.

## What It Does

Async TCP client that connects to the daemon, handles the greeting flow, and provides an interactive chat loop with commands.

## Key Class: EidolonClient

- **`connect()`** -- Opens TCP connection to daemon (default 127.0.0.1:7777).
- **`run()`** -- Full client lifecycle: connect, send being selection, receive greeting (handling pending_notifications first), input loop with `/sleep`, `/wake`, `/status` commands, quit/exit. (Source: `client/chat_client.py:92-170`)
- **`_display(msg)`** -- Renders server messages by type: response, status, queued, pending_notifications, error.

## Standalone Functions

- **`peek(host, port)`** -- Quick status check without starting a session. Sends `{"type": "peek"}`, displays formatted status. (Source: `client/chat_client.py:173-196`)
- **`_display_peek(data)`** -- Renders peek response: state, fatigue, uptime, notifications, queued messages.

## Usage

```bash
python3 -m client.chat_client              # Interactive chat
python3 -m client.chat_client --peek       # Quick status
python3 -m client.chat_client --being Eidolon  # Specify being name
```

## Dependencies

`asyncio`, `json`, `argparse`

See also: [daemon_server](daemon_server.md), [client_chat](client_chat.md)
