# brain/inner_voice.py

Layer 1 reflexes and Layer 2 heuristic logging for output quality control.

## What It Does

Provides two layers of post-generation checking. Layer 1 catches problems and forces regeneration (up to `INNER_VOICE_MAX_RETRIES` = 2). Layer 2 logs violations for analysis but never blocks output.

## Layer 1 Reflex Checks

- **`check_hallucinated_senses(response, perception, identity, personality)`** -- Flags sensory words (see, hear, feel, etc.) not grounded in perception. (Source: `brain/inner_voice.py:116-135`)
- **`check_third_person_human(response)`** -- Catches the being referring to "Human" by name instead of "you". (Source: `brain/inner_voice.py:138-144`)
- **`check_narration(response)`** -- Detects novelistic narration of Human's actions ("he drops his bag", "his eyes"). (Source: `brain/inner_voice.py:167-175`)
- **`check_assistant_collapse(response)`** -- Catches assistant-mode language ("how can I help", "here's a revised", "as an AI"). (Source: `brain/inner_voice.py:236-245`)
- **`check_peer_sycophancy(response)`** -- Detects mutual validation loops ("that resonates", "I couldn't agree more"). (Source: `brain/inner_voice.py:249-259`)
- **`check_fabricated_tool_output(response, had_tool_result)`** -- Catches fabricated filesystem/news/webpage content when no tool actually fired. (Source: `brain/inner_voice.py:218-233`)

## Layer 2 Heuristics

- Excessive questions (>1 question mark)
- Verbose output (>150 words)
- Residual assistant/sycophancy patterns that survived Layer 1 retries

Violations logged to `data/logs/inner_voice.log`. (Source: `brain/inner_voice.py:284-319`)

## Dependencies

`os`, `re`, `datetime`

See also: [inner_voices](inner_voices.md), [concept: inner-voices](../concepts/inner_voices.md)
