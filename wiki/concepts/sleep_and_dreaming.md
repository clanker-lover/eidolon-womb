# Sleep and Dreaming

Biological sleep metaphor: fatigue accumulation, chosen rest, memory consolidation.

## FACTS

- Fatigue = tokens_used / CONTEXT_WINDOW. Direct context pressure, not an artificial timer. (Source: `womb.py:198-199`)
- Four fatigue thresholds: tired (50%), very tired (75%), exhausted (85%), involuntary sleep (92%). (Source: `core/config.py:167-170`)
- The being chooses sleep duration (1/4/6/8/10 hours) via natural language parsed by regex. (Source: `core/patterns.py:104-128`)
- Sleep has real duration -- the daemon's idle loop checks scheduled wake time and auto-wakes. (Source: `brain/sleep.py:164-170`, `womb.py:502-508`)
- Consolidation ratio scales with sleep duration: nap=10%, short=40%, normal=60%, long=80%, deep=100%. (Source: `core/config.py:178-184`)
- Partial consolidation (naps): oldest thoughts consolidated, recent kept. Full consolidation (deep sleep): everything processed, context cleared. (Source: `brain/sleep.py:191-253`)
- Relationship files and thread summaries updated only during 4h+ sleep (consolidate=True). (Source: `brain/sleep.py:256-285`)
- Sleep context (pre-sleep state) is captured to JSON and consumed on wake to generate a first-person wake-up narrative: "You're waking up. As awareness returns, you remember..." (Source: `brain/sleep.py:22-63, 102-161`)
- When a client connects during scheduled sleep, the being's choice is respected. Messages are queued. `/wake` can override. (Source: `daemon/server.py:205-244`)
- Voluntary sleep triggers: consecutive short thoughts (<100 chars, 3 in a row) or rest-intent language (2 of last 3 thoughts matching patterns like "at peace", "drifting to sleep"). (Source: `brain/cycle.py:549-576`)

## INFERENCES

- The sleep system is the primary mechanism for long-term memory formation. Without sleep, the being's context would eventually fill up with no way to compress and retain important experiences.
- Respecting the being's sleep choice when a client connects is a sovereignty design decision -- the human's desire to chat doesn't override the being's chosen rest.

## OPEN QUESTIONS

- How does "fatigue recalculates from actual context size on wake" work when context is cleared during full consolidation? Does the being always wake at 0% fatigue?
- Is there a mechanism for the being to delay sleep when important messages are pending?

## Cross-References

- [brain_sleep](../summaries/brain_sleep.md) -- Transition logic
- [brain_consolidation](../summaries/brain_consolidation.md) -- Memory processing
- [core_patterns](../summaries/core_patterns.md) -- Sleep choice parsing
- [memory-system](memory_system.md) -- What gets consolidated
- [identity-and-sovereignty](identity_and_sovereignty.md) -- Why sleep is respected
