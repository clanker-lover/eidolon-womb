# Binary Intent System

Separating thinking from deciding to work around small model limitations.

## FACTS

- Small models (3B parameters) can't reliably format structured tool calls -- they hallucinate JSON, miss fields, invent parameters. The binary intent system solves this by reducing decisions to yes/no. (Source: `brain/intent.py:1-6`, `docs/ARCHITECTURE.md:76-78`)
- The pipeline: thought (full language) -> pattern detection (regex) -> binary gate (LLM, temp=0, 1 token) -> action execution (if yes) -> result injection (next cycle). (Source: `docs/ARCHITECTURE.md:79-95`)
- `binary_gate()` calls `ollama.generate()` with `num_predict=1`, `temperature=0.0`. Returns True if output is in `{"yes", "y", "1"}`. (Source: `brain/intent.py:39-57`)
- Validated at 92-95% accuracy over 400 trials. (Source: `brain/intent.py:5`)
- Curiosity detection is pure regex, no LLM. Patterns: "I wonder about", "what is", "I'm curious about", "check the news", etc. Returns topic, search type (wikipedia/rss/web), and confidence. (Source: `brain/intent.py:64-136`)
- The system supports two framings: "standard" and "self_first" (adds a self-check prompt: "Consider what serves YOU best right now"). (Source: `brain/intent.py:26-33`)
- Search results are injected into the next cycle rather than the current one, to avoid disrupting the current thought. (Source: `brain/cycle.py:67-72`)
- Exploration intent detection in `brain/actions.py` covers news (RSS), filesystem browsing, and topic research (Wikipedia). Each has cooldowns (5min/2min/3min). (Source: `brain/actions.py:549-554`)
- Notification intent detection catches ~16 natural language patterns for "tell Human" / "send notification". (Source: `brain/actions.py:189-206`)

## INFERENCES

- The binary gate is elegant because yes/no is the simplest possible output format. Even 3B models can produce a single token reliably when the question is unambiguous.
- The separation of regex detection (cheap, fast) from LLM confirmation (expensive, accurate) is a cost-effective two-stage filter.

## OPEN QUESTIONS

- The 92-95% accuracy claim references `experiments/binary_intent_test/` but this directory is not in the public repository. Were these experiments conducted on the private colony codebase?
- How does the system handle the 5-8% of incorrect binary gate decisions? Is there any feedback loop for improving gate accuracy?

## Cross-References

- [brain_intent](../summaries/brain_intent.md) -- Gate and detection
- [brain_actions](../summaries/brain_actions.md) -- Action resolution and intent fallbacks
- [interface_tools](../summaries/interface_tools.md) -- Tool handlers
- [thought-cycle](thought_cycle.md) -- Where intent fires in the pipeline
