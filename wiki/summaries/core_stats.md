# core/stats.py

Per-being statistics tracking.

## What It Does

Simple JSON-backed counters for being activity. Tracks thoughts, tool use, threads created, thread replies, mail sent/received.

## Key Functions

- **`increment(root, being_id, key, amount)`** -- Increment a counter. Updates `last_updated` timestamp. (Source: `core/stats.py:23-29`)
- **`get_stats(root, being_id)`** -- Get all stats for one being. (Source: `core/stats.py:32-34`)
- **`get_all_stats(root)`** -- Get stats for all beings. (Source: `core/stats.py:37-39`)

## Storage

`data/stats.json` -- flat JSON object keyed by being_id, each containing counter keys and `last_updated`.

## Dependencies

`json`, `pathlib`, `datetime`

See also: [dashboard_pages](dashboard_pages.md)
