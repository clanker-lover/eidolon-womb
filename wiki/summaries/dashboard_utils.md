# dashboard/utils.py

Shared helpers for the womb dashboard.

## What It Does

Utility functions used across all dashboard pages: daemon communication, thread store access, user config, timestamp formatting, file helpers.

## Key Functions

- **`peek_daemon(host, port)`** -- TCP socket peek to daemon. Returns parsed JSON or None. (Source: `dashboard/utils.py:35-51`)
- **`send_thread_reply(being, thread_id, content)`** -- Sends thread_reply message to daemon with 60s timeout. (Source: `dashboard/utils.py:54-89`)
- **`send_daemon_command(command)`** -- Sends command message (sleep/wake/stasis/normal/status). (Source: `dashboard/utils.py:92-115`)
- **`get_thread_store()`** -- Returns `ThreadStore` instance for `data/threads/`. (Source: `dashboard/utils.py:28-32`)
- **`load_user_config()` / `save_user_config(config)`** -- JSON config at `data/user_config.json`. (Source: `dashboard/utils.py:121-134`)
- **`get_user_name()`** -- Returns configured display name, defaulting to "Human". (Source: `dashboard/utils.py:137-139`)
- **`format_timestamp(iso_string)`** -- Relative formatting: "just now", "5m ago", "2h ago", "3d ago". (Source: `dashboard/utils.py:150-170`)

## Dependencies

`json`, `socket`, `core.config` (DAEMON_PORT), `core.threads` (ThreadStore), `core.stats`

See also: [dashboard_app](dashboard_app.md)
