# brain/context.py

Priority-tiered context assembly within the token budget.

## What It Does

Packs all available context (perception, identity, personality, facts, memories, history) into the LLM's context window using a priority system. Higher-priority content is never trimmed; lower-priority content is dropped when space runs out.

## Key Functions

- **`assemble_messages(perception, identity, personality, human_facts, learned_facts, history, user_message, session_summaries, retrieved_memories)`** -- Main assembler. Returns `(messages_list, tokens_used)`. (Source: `brain/context.py:11-115`)
- **`assemble_thread_context(...)`** -- Separate assembler for thread replies with smaller budget (12,000 tokens). Includes relationship file and thread summary. (Source: `brain/context.py:118-196`)
- **`estimate_tokens(text)`** -- Simple character-based estimation: `len(text) // CHARS_PER_TOKEN`. (Source: `brain/context.py:7-8`)

## Priority Tiers

| Priority | Content | Behavior |
|----------|---------|----------|
| P0 | Perception + Identity + Guardrails | Never trimmed |
| P1 | User message | Never trimmed |
| P2 | Personality | Whole or dropped |
| P3 | Facts (seed first, learned newest-first) | Per-line truncation |
| P4 | Retrieved memories | Per-item truncation |
| P5 | Session summaries | Oldest-first truncation |
| P6 | Conversation history | Most-recent-first until budget |

## Configuration

- `MAX_PROMPT_TOKENS` = 15,872 (general context)
- `THREAD_CONTEXT_MAX` = 12,000 (thread replies)
- `CHARS_PER_TOKEN` = 4

## Architectural Role

The context assembler is the bottleneck between what the being knows and what fits in a single inference call. The priority system ensures identity and perception always survive, while older or lower-relevance content gets trimmed gracefully.

See also: [concept: context-priority-system](../concepts/context_priority_system.md), [brain_retrieval](brain_retrieval.md)
