# inner_voices.py

Cold (rational correction) and hot (restless provocation) inner voices.

## What It Does

Implements two competing internal voices that speak into the being's thought stream. Neither controls the being -- they inject feedback for the next cycle. Cold voice catches fabricated experiences. Hot voice breaks abstract philosophy loops. (Source: `inner_voices.py:1-6`)

## Cold Voice

- **`should_cold_fire(thought, perception, retrieved_memories, being_name)`** -- Checks 4 categories: fabrication patterns ("I've been experimenting"), sensory hallucination (claims not in perception), experience recall ("I remember when" -- always fabricated since the being has no experiential memory), and identity violations (wrong name, third-person self-reference, speaking as Human). (Source: `inner_voices.py:46-80`)
- **`run_cold_voice(thought, perception, retrieved_memories)`** -- Generates a 1-2 sentence correction at temperature 0.1. (Source: `inner_voices.py:197-212`)

## Hot Voice

- **`should_hot_fire(thought, previous_thoughts, cycles_since_tool_use)`** -- Requires ALL of last `LOOKBACK_COUNT` (3) thoughts to be >= threshold (0.65 Jaccard) similar, plus a grace period of `MIN_STALE_CYCLES` (10). Supports semantic mode via embeddings. (Source: `inner_voices.py:136-171`)
- **`run_hot_voice(thought, affordances)`** -- Generates a provocative 1-2 sentence push toward concrete action at temperature 0.95. (Source: `inner_voices.py:215-225`)

## Orchestrator

- **`run_inner_voices(...)`** -- At most one voice fires per cycle. Cold has priority. Suppressed when tool tags fired (being just acted). Returns `(voice_name, voice_output)` or `(None, None)`. (Source: `inner_voices.py:256-294`)

## Utility Functions

- **`cosine_similarity(vec_a, vec_b)`** -- Manual dot-product cosine similarity.
- **`word_overlap_ratio(text_a, text_b)`** -- Jaccard similarity between word sets.

## Dependencies

`ollama`, `config` (voice temperatures, pattern lists, thresholds), `brain.perception` (AFFORDANCES_BLOCK)

See also: [brain_inner_voice](brain_inner_voice.md), [concept: inner-voices](../concepts/inner_voices.md)
