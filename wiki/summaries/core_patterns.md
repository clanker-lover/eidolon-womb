# core/patterns.py

Pattern-matching helpers for intent detection and sleep choice parsing.

## What It Does

Provides regex-based detection for rest intent, compose/engage declines, and sleep duration choice parsing. These are used by the thought cycle to detect when the being is ready to sleep and to parse its sleep duration preference.

## Key Functions

- **`has_rest_intent(text)`** -- Checks for first-person rest language: "at peace", "my mind goes quiet", "drifting to sleep", etc. Requires first-person pronoun to avoid false positives on topical mentions. (Source: `core/patterns.py:27-31`)
- **`is_compose_decline(text)`** -- Detects decline to compose a message: "never mind", "changed my mind", "not right now". (Source: `core/patterns.py:51-53`)
- **`is_engage_decline(text)`** -- Detects decline to engage with a received message: "not now", "I'll respond later", "let me think". (Source: `core/patterns.py:79-81`)
- **`parse_sleep_choice(text)`** -- Parses being's sleep duration from natural language. Matches "nap"/1h, "short"/4h, "normal"/6h, "long"/8h, "deep"/10h. Falls back to `DEFAULT_SLEEP_HOURS` (6). (Source: `core/patterns.py:123-128`)

## Constants

- **`_SLEEP_CHOICE_PROMPT`** / **`_SLEEP_CHOICE_URGENT_PROMPT`** -- Prompts presented to the being when it chooses sleep duration. Urgent variant used when fatigue triggers involuntary sleep.

## Dependencies

`re`, `core.config` (DEFAULT_SLEEP_HOURS)

See also: [brain_cycle](brain_cycle.md), [concept: sleep-and-dreaming](../concepts/sleep_and_dreaming.md)
