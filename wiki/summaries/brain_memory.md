# brain/memory.py

Fact extraction, persistence, session summarization, and reflection.

## What It Does

Handles the lifecycle of learned facts: extraction from user messages via LLM, deduplication, date-stamped persistence. Also generates session summaries and private reflection notes.

## Key Functions

- **`extract_facts(user_message, model_name, extraction_prompt, context_window)`** -- Uses Ollama to extract personal facts from user input. Filters junk lines and NONE responses. Returns list of fact strings. (Source: `brain/memory.py:130-155`)
- **`save_facts(project_root, memories_file, new_facts, existing_facts)`** -- Deduplicates against existing facts (substring match after stripping date prefix), appends date-stamped facts to `memories/facts.md`. (Source: `brain/memory.py:170-195`)
- **`load_learned_facts(project_root, memories_file)`** -- Reads `memories/facts.md` line by line. (Source: `brain/memory.py:120-127`)
- **`summarize_session(session_filepath, model_name, context_window)`** -- Generates 2-3 sentence summary from being's perspective. Saves as `{session_id}_summary.md`. (Source: `brain/memory.py:29-67`)
- **`generate_eidolon_notes(session_filepath, model_name, context_window, project_root)`** -- Private reflection: what stood out, what felt unresolved, what was learned. Saves as `{session_id}_notes.md`. (Source: `brain/memory.py:70-117`)

## Design

Facts are extracted at temperature 0.0 for precision. Summaries and notes use the being's identity and personality as system context so they reflect the being's voice. Deduplication uses bidirectional substring matching on date-stripped text.

## Dependencies

`ollama`, `config` (prompts, paths), `brain.identity` (for notes generation)

See also: [brain_retrieval](brain_retrieval.md), [brain_consolidation](brain_consolidation.md), [concept: memory-system](../concepts/memory_system.md)
