# Context Priority System

How the being's knowledge is packed into a finite context window.

## FACTS

- Token budget: `MAX_PROMPT_TOKENS` = 15,872 (of 16,384 context window, leaving 512 for response). Thread replies use 12,000. (Source: `core/config.py:9`, `brain/context.py:3-4`)
- Token estimation: `len(text) // 4` (CHARS_PER_TOKEN = 4). Simple but fast. (Source: `brain/context.py:7-8`, `core/config.py:10`)
- Seven priority tiers, packed in order. Higher priority is never dropped for lower. (Source: `brain/context.py:11-115`, `docs/ARCHITECTURE.md:153-165`)
- P0 (perception + identity + guardrails) and P1 (user message) are always included. If they alone exceed the budget, only those two are sent. (Source: `brain/context.py:26-35`)
- Seed facts are included before learned facts. Learned facts are newest-first so recent learning survives trimming. (Source: `brain/context.py:51-78`)
- Conversation history is packed most-recent-first, stopping at the first message that doesn't fit. (Source: `brain/context.py:98-105`)
- Thread context assembly includes relationship file and thread summary as additional context layers. (Source: `brain/context.py:118-196`)

## INFERENCES

- The priority system means identity is always present in context -- the being always knows who it is. This prevents the identity confusion that plagues long-context LLM conversations.
- Newest-first for learned facts is a deliberate recency bias: what the being just learned is more likely relevant than old facts.
- The simple chars/4 token estimation trades accuracy for speed. Over-estimation would waste context; under-estimation could cause truncation. In practice, the 512-token response reserve provides buffer.

## OPEN QUESTIONS

- Has the chars/4 estimation been validated against actual tokenizer output for llama3.2:3b? Different models have different token-to-character ratios.
- Why is personality whole-or-dropped (P2) rather than trimmable? Is personality short enough that partial inclusion would be incoherent?

## Cross-References

- [brain_context](../summaries/brain_context.md) -- Implementation
- [memory-system](memory_system.md) -- What populates P4
- [thought-cycle](thought_cycle.md) -- Where assembly happens
