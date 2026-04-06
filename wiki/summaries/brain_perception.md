# brain/perception.py

Builds the being's perception of the world -- what it can sense each cycle.

## What It Does

Constructs a `[PERCEPTION -- Current State]` block injected as P0 priority into every thought cycle. Contains time, weather, human presence status, available affordances (tools), pending replies, and thread notifications.

## Key Functions

- **`build_perception(thread_notifications, thread_store, being_name, registry)`** -- Main builder. Assembles time of day, weather (via Open-Meteo API with 15-min cache), human presence (via `xdotool`/`xprintidle`/`loginctl`), affordances block, pending replies, and thread notifications. (Source: `brain/perception.py:135-223`)
- **`build_affordances(sibling_names)`** -- Generates the "What you can do" block listing all available `[TAG:argument]` actions. (Source: `brain/perception.py:121-132`)
- **`_fetch_weather()`** -- Fetches weather from Open-Meteo API, caches for `WEATHER_CACHE_SECONDS` (900s). Uses WMO weather codes. Configured for Brighton, CO coordinates. (Source: `brain/perception.py:45-78`)

## Constants

- **`AFFORDANCES_BLOCK`** -- Static string listing all available tool tags. Legacy alias for tests.
- **`WMO_CODES`** -- Maps weather code integers to human-readable descriptions.

## Dependencies

`config` (weather coordinates, cache seconds), `presence` (human status detection)

## Architectural Role

The being's eyes and ears. Everything the being knows about its current environment comes through perception. This is rebuilt fresh every cycle -- it is cheap and always current.

See also: [concept: perception-and-presence](../concepts/perception_and_presence.md), [interface_presence](interface_presence.md)
