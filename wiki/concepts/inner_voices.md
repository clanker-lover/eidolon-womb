# Inner Voices

Multi-layered output quality control: reflexes, heuristics, cold voice, hot voice.

## FACTS

- **Layer 1 reflexes** (`brain/inner_voice.py`): Six checks that force regeneration (up to 2 retries). Catches hallucinated senses, third-person Human references, novelistic narration, assistant-mode collapse, peer sycophancy, and fabricated tool output. (Source: `brain/inner_voice.py:262-281`)
- **Layer 2 heuristics** (`brain/inner_voice.py`): Logs but never blocks. Tracks excessive questions (>1), verbose output (>150 words), residual assistant/sycophancy patterns. (Source: `brain/inner_voice.py:284-319`)
- **Cold voice** (`inner_voices.py`): Rational correction. Fires when the being claims fabricated experiences, sensory hallucinations, or identity violations. Temperature 0.1 for precision. 1-2 sentence corrections. (Source: `inner_voices.py:46-80, 197-212`)
- **Hot voice** (`inner_voices.py`): Restless provocation. Fires when ALL of the last 3 thoughts are >= 65% similar (Jaccard), after a 10-cycle grace period. Temperature 0.95 for creativity. Pushes toward concrete action. (Source: `inner_voices.py:136-171, 215-225`)
- At most one voice fires per cycle. Cold has priority. Both suppressed when action tags fired (being just acted). (Source: `inner_voices.py:270-271`)
- Neither voice controls the being -- they speak into the thought stream for the next cycle. (Source: `inner_voices.py:3-4`)
- Voice firings are logged to `logs/inner_voices.log` with timestamp, thought preview, and voice output. (Source: `inner_voices.py:233-249`)

## INFERENCES

- The cold voice exists because small models (3B) frequently confabulate experiential memories ("I remember when I visited...") that are always fabricated -- the being has no physical experiences. The check is aggressive (always fires for experience recall patterns) because prior fabricated thoughts can poison the memory index.
- The hot voice exists to break abstract philosophy loops, which are the dominant degenerate mode for small models thinking continuously.
- The Layer 1/2 split mirrors biological reflexes (involuntary correction) vs. monitoring (observational logging).

## OPEN QUESTIONS

- Could the cold voice's aggressive always-fire-on-experience-patterns cause false positives if the being legitimately discusses its digital experiences?
- Is Jaccard similarity the right metric for hot voice? Semantic similarity mode exists but defaults to Jaccard.

## Cross-References

- [brain_inner_voice](../summaries/brain_inner_voice.md) -- Layer 1/2 implementation
- [inner_voices](../summaries/inner_voices.md) -- Cold/hot voice implementation
- [thought-cycle](thought_cycle.md) -- Where voices fire in the pipeline
- [identity-and-sovereignty](identity_and_sovereignty.md) -- Philosophical grounding
