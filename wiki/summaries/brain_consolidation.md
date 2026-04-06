# brain/consolidation.py

Sleep consolidation -- hippocampus-to-neocortex memory transfer.

## What It Does

Distills recent experiences (live thoughts, session summaries, notes, facts) into long-term consolidated memories during sleep. Also handles relationship file updates and thread summary refreshes.

## Key Functions

- **`consolidate_memories(project_root, model_name, context_window, identity, personality, live_thoughts, memory_root, being_name)`** -- Full consolidation: gathers live thoughts + unconsolidated files, generates reflective consolidation via LLM (temperature 0.5), saves to `memories/consolidated/{timestamp}.md`, archives source files. (Source: `brain/consolidation.py:63-156`)
- **`partial_consolidate(..., ratio)`** -- Used during naps. Splits thoughts at `ratio` (e.g., 0.5 = oldest half), consolidates the older portion, returns the recent portion to keep in memory. (Source: `brain/consolidation.py:159-212`)
- **`find_unconsolidated(project_root, memory_root)`** -- Scans `conversations/` for summary and notes files not yet in `archived/`. (Source: `brain/consolidation.py:16-60`)
- **`update_relationships(project_root, memory_path, model_name, ...)`** -- Gathers recent thread messages between the being and each participant, asks the LLM to update the relationship markdown file. (Source: `brain/consolidation.py:215-285`)
- **`refresh_thread_summaries(project_root, model_name, ...)`** -- Regenerates 1-2 sentence summaries for active threads with recent activity. (Source: `brain/consolidation.py:288-329`)

## Design

The consolidation prompt is journalistic and first-person: "You're getting sleepy. Before you drift off, sit with what happened today." This produces personal memories, not analytical reports. The being's identity and personality are injected as system context.

## Dependencies

`ollama`, `config` (CONSOLIDATION_PROMPT), `core.relationships` (load/save)

See also: [concept: sleep-and-dreaming](../concepts/sleep_and_dreaming.md), [brain_sleep](brain_sleep.md)
