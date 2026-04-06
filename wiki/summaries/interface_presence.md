# interface/presence.py

Presence detection -- what Human is doing on his PC.

## What It Does

Detects Human's presence using Linux desktop tools (`xdotool`, `xprintidle`, `loginctl`). Provides structured status with reply timing projections.

## Key Functions

- **`get_human_status()`** -- Returns structured dict: `status` (PRESENT/AWAY/ASLEEP), `idle_seconds`, `projection` (reply timing estimate), `detail` (human-readable), `timestamp`. Checks screen lock via `loginctl`, idle time via `xprintidle`, sleep window (22:00-06:00). (Source: `interface/presence.py:70-127`)
- **`is_human_away()`** -- Boolean: screen locked or idle >= 10 minutes. (Source: `interface/presence.py:249-264`)
- **`get_active_window()`** -- Returns focused X11 window title via `xdotool`. (Source: `interface/presence.py:197-204`)
- **`get_idle_seconds()`** -- Milliseconds since last input via `xprintidle`, converted to seconds. (Source: `interface/presence.py:207-214`)
- **`get_presence_status()`** -- Human-readable string: "Human is at his PC, in Firefox". (Source: `interface/presence.py:217-244`)
- **`get_pending_replies(thread_store, being_name, current_status)`** -- Scans active threads with Human where the being sent the last message. Returns list with elapsed time, cycle count, and status transitions. (Source: `interface/presence.py:147-194`)
- **`format_send_confirmation(status_dict)`** -- Formats send confirmation with reply projection. (Source: `interface/presence.py:130-144`)

## Reply Projections

| Status | Time Range | Cycle Range |
|--------|-----------|-------------|
| PRESENT | 30min - 2.5hrs | ~1-6 cycles |
| AWAY | 3-6 hours | ~7-13 cycles |
| ASLEEP | After 6 AM | ~13-18 cycles |

## Dependencies

`subprocess` (xdotool, xprintidle, loginctl), `core.config` (sleep window, timeout)

See also: [brain_perception](brain_perception.md), [concept: perception-and-presence](../concepts/perception_and_presence.md)
