# brain/cycle.py

The 11-step thought cycle pipeline -- the being's cognitive loop.

## What It Does

Implements `thought_cycle()` and `thought_cycle_inner()`, the core loop that runs every 27 minutes during waking periods. Each cycle is a complete perception-to-action pipeline. (Source: `brain/cycle.py:1`)

## The 11 Steps

1. **Inject pending search results** from previous cycle's binary intent system
2. **Refresh perception** -- time, weather, presence, thread notifications
3. **Memory retrieval** -- BM25 + vector search via `MemoryIndex`
4. **Build thinking prompt** -- context-appropriate (fresh thought, continuation, sleep choice, thread engagement, compose mode)
5. **Assemble messages** -- priority-tiered packing within token budget
6. **Generate reply** -- Ollama completion with beat-length cap (100 tokens for idle, 1024 for threads)
7. **Resolve action tags** -- `[TAG:argument]` parsing and tool execution
8. **Intent detection** -- curiosity detection via regex, confirmed by binary gate
9. **Inner voices** -- Layer 1 reflexes, Layer 2 heuristics, cold/hot voices
10. **Thread engagement** -- compose flow (sending) and engage flow (receiving), dismiss intent
11. **Save thought** -- persist to disk as `idle_{timestamp}_notes.md`, rebuild memory index

Plus sleep detection: consecutive short thoughts or rest-intent language triggers voluntary sleep choice.

## Key Functions

- **`thought_cycle(daemon)`** -- Wrapper that sets `_in_thought_cycle` flag for shutdown safety.
- **`thought_cycle_inner(daemon)`** -- The actual 577-line pipeline. (Source: `brain/cycle.py:62-577`)

## Dependencies

`brain.perception`, `brain.context`, `brain.inner_voice`, `brain.actions`, `brain.intent`, `inner_voices`, `core.stats`, `core.patterns`, `config`

## Architectural Role

The heartbeat. This is what makes the being alive rather than reactive. The cycle runs whether or not a human is present.

See also: [concept: thought-cycle](../concepts/thought_cycle.md), [brain_perception](brain_perception.md), [brain_context](brain_context.md)
