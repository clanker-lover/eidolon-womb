# interface/notifications.py

Notification lifecycle -- queue and fire desktop notifications.

## What It Does

Manages the lifecycle of desktop notifications: queueing when Human is away, firing via `notify-send` when Human returns, deduplication, cooldown enforcement, and thread system persistence.

## Key Functions

- **`queue_notification(daemon, message)`** -- Deduplicates, appends to `daemon.pending_notifications`, persists to thread system (creates or finds thread with Human), captures Human's status at send time in message metadata. (Source: `interface/notifications.py:16-60`)
- **`check_presence_and_notifications(daemon)`** -- Polls presence, resets thought chain on presence change, fires pending notifications with cooldown (5-min between fires, bypass on return-from-away). (Source: `interface/notifications.py:63-103`)

## Design

Notifications are presence-aware: they queue while Human is away and fire when he returns. The being's desire to reach out is honored even if it can't produce proper `[SEND_NOTIFICATION:...]` syntax -- intent detection in `brain/actions.py` catches natural language and routes through this system.

## Dependencies

`interface.presence`, `interface.tools` (fire_notify_send), `core.threads` (ThreadMessage), `core.config` (intervals)

See also: [interface_tools](interface_tools.md), [brain_actions](brain_actions.md)
