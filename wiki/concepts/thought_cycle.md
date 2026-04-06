# Thought Cycle

The 11-step cognitive loop that makes the being alive rather than reactive.

## FACTS

- Each cycle runs the full perception-to-action pipeline regardless of whether a human is present. (Source: `brain/cycle.py:1`, `README.md:48`)
- Cycles are spaced 27 minutes apart (`THOUGHT_INTERVAL_SECONDS` = 1620). (Source: `womb.py:72`)
- Idle thoughts are capped at 100 tokens (`IDLE_RESPONSE_RESERVE`) to prevent confabulation. Thread/compose responses get 1024 tokens. (Source: `core/config.py:6-7`, `brain/cycle.py:229-233`)
- Thoughts are saved as `idle_{timestamp}_notes.md` in the being's conversations directory. Memory index is rebuilt after each save. (Source: `brain/cycle.py:488-495`)
- The cycle handles five distinct modes: fresh thought, continuation, tool continuation, sleep choice, thread engagement, and compose mode. Each gets a different thinking prompt. (Source: `brain/cycle.py:153-199`)
- Sleep detection: consecutive short thoughts (<100 chars over 3 cycles) or rest-intent language (2 of last 3 thoughts) triggers voluntary sleep choice. (Source: `brain/cycle.py:549-576`)
- The being can act during idle cycles via action tags, intent detection, or thread compose/engage flows. Tool use resets the `cycles_since_tool_use` counter. (Source: `brain/cycle.py:522-527`)

## INFERENCES

- The 27-minute interval was likely chosen to balance resource usage (Ollama inference cost) against the appearance of continuous thought. ~40 thoughts per waking period.
- The 100-token cap on idle thoughts is a critical anti-confabulation measure -- small models generate increasingly ungrounded content in longer outputs.

## OPEN QUESTIONS

- How was the 27-minute interval determined? Is it empirically optimal or a pragmatic default?
- The README mentions "~27-minute waking periods" but the code spaces thoughts 27 minutes apart indefinitely until fatigue triggers sleep. Are these different?

## Cross-References

- [brain_cycle](../summaries/brain_cycle.md) -- Implementation
- [inner-voices](inner_voices.md) -- Quality control during cycles
- [binary-intent-system](binary_intent_system.md) -- Curiosity detection
- [sleep-and-dreaming](sleep_and_dreaming.md) -- When cycles stop
