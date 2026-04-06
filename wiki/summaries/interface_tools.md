# interface/tools.py

Tool functions invoked via action tags.

## What It Does

Implements all tool handlers registered in `TOOL_REGISTRY`. Each function takes an optional string argument and returns a plain text result.

## Tool Registry

| Tag | Function | Description |
|-----|----------|-------------|
| `CHECK_WINDOW` | `tool_check_window()` | Active X11 window title |
| `LIST_DIR` | `tool_list_dir(path)` | Directory listing with sizes (max 50 entries) |
| `READ_FILE` | `tool_read_file(path)` | File contents (max 8KB) |
| `FETCH_RSS` | `tool_fetch_rss(feed)` | RSS headlines (15-min cache). 5 feeds: AP News, Reuters, Ars Technica, Lifehacker, Nature |
| `FETCH_WEBPAGE` | `tool_fetch_webpage(url)` | Article extraction via trafilatura (max 6000 chars) |
| `SEND_NOTIFICATION` | `tool_send_notification(msg)` | Desktop notification via `notify-send` with optional sound |
| `START_THREAD` | `tool_start_thread(arg)` | Create thread: `participant|subject|message` |
| `RESPOND_THREAD` | `tool_respond_thread(arg)` | Reply to thread: `thread_id|message` |
| `DISMISS_THREAD` | `tool_dismiss_thread(arg)` | Mark thread as handled |
| `SEARCH_THREADS` | `tool_search_threads(arg)` | Search thread messages: `thread_id|query` |

## Module-Level State

Daemon injects these at startup via `daemon/lifecycle.py`:
- `_notification_sink` -- Callback to `daemon._queue_notification()`
- `_thread_store` -- Reference to `ThreadStore`
- `_active_being_name` / `_active_being_id`
- `_get_human_status` -- Reference to presence function

## Dependencies

`os`, `subprocess` (notify-send, paplay), `interface.presence`, `feedparser` (optional), `trafilatura` (optional)

See also: [brain_actions](brain_actions.md), [concept: binary-intent-system](../concepts/binary_intent_system.md)
