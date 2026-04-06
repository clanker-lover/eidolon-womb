# brain/intent.py

Binary intent system -- curiosity detection and search via yes/no gate.

## What It Does

Implements the binary gate (yes/no LLM query) and curiosity detection (regex-based pattern matching). This solves the problem of small models being unable to reliably format structured tool calls. Validated at 92-95% accuracy over 400 trials. (Source: `brain/intent.py:1-6`)

## Key Functions

- **`binary_gate(model, context, question, framing)`** -- Asks a yes/no question via `ollama.generate()` with `temperature=0.0` and `num_predict=1`. Returns boolean. Supports "standard" and "self_first" framings. (Source: `brain/intent.py:39-57`)
- **`detect_curiosity(thought)`** -- Pure regex, no LLM. Scans for patterns like "I wonder about", "what is", "I'm curious about", "check the news". Returns `{topic, search_type, confidence}` or None. Filters negation patterns ("I was", "if I", "the concept of curiosity"). (Source: `brain/intent.py:108-136`)
- **`process_curiosity(model, being_context, curiosity, framing)`** -- Async orchestrator: gates curiosity through `binary_gate()`, then fetches Wikipedia or RSS content. Returns formatted search result for injection into next cycle. (Source: `brain/intent.py:144-182`)

## Design

The key insight: separate thinking (full language) from deciding (single token). The model thinks freely, regex detects intent, then a 1-token LLM call confirms. This avoids the 50%+ failure rate of structured output on 3B models.

## Dependencies

`ollama`, `config` (CONTEXT_WINDOW, INTENT_MAX_RESULT_CHARS), `tools` (tool_fetch_webpage, tool_fetch_rss), `brain.actions` (_extract_topic, _topic_to_wikipedia_url, _topic_to_feed)

See also: [concept: binary-intent-system](../concepts/binary_intent_system.md), [brain_actions](brain_actions.md)
