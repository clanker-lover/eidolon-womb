# client/monitor.py

Terminal monitor for the womb daemon.

## What It Does

Connects to the daemon via peek protocol and displays a formatted status view with ANSI colors. Supports single-shot and auto-refresh (watch) modes.

## Key Functions

- **`render(data)`** -- Formats peek data into colored terminal output: state (awake/asleep with icon), fatigue bar (green/yellow/red), uptime or sleep countdown, thought count, last thought preview, last transition, pending notifications/queued messages. (Source: `client/monitor.py:61-153`)
- **`run_once(host, port)`** -- Single status fetch and render. (Source: `client/monitor.py:169-183`)
- **`run_watch(host, port, interval)`** -- Auto-refresh loop with screen clear. Default 5s interval. (Source: `client/monitor.py:186-214`)

## Usage

```bash
python3 -m client.monitor              # Single check
python3 -m client.monitor --watch      # Auto-refresh every 5s
python3 -m client.monitor --interval 10  # Custom refresh interval
```

## Dependencies

`asyncio`, `json`, `datetime`

See also: [daemon_server](daemon_server.md) (peek protocol)
