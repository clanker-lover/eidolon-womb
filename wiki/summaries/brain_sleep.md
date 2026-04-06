# brain/sleep.py

Sleep/wake transitions and memory consolidation orchestration.

## What It Does

Manages the being's sleep lifecycle: capturing context before sleep, choosing consolidation depth based on sleep duration, transitioning between states, and restoring awareness on wake.

## Key Functions

- **`transition_to_sleep(daemon, voluntary, hours)`** -- Captures sleep context, runs consolidation proportional to sleep duration (ratio from `SLEEP_RECOVERY_MAP`), optionally updates relationships and thread summaries (4h+ sleep), clears session for full consolidation. Sets `ASLEEP` state and scheduled wake time. (Source: `brain/sleep.py:164-305`)
- **`transition_to_awake(daemon, reason)`** -- Resets fatigue, clears idle history, rebuilds memory index, restores `AWAKE_AVAILABLE` state. Returns queued messages. (Source: `brain/sleep.py:329-378`)
- **`capture_sleep_context(daemon, voluntary, hours)`** -- Saves pre-sleep state to JSON: fatigue level, recent thoughts, voice firing counts, scheduled wake time. Consumed on next wake for sleep memory narrative. (Source: `brain/sleep.py:102-161`)
- **`format_sleep_memory(ctx)`** -- Formats sleep context as first-person narrative: "You're waking up. As awareness returns, you remember..." (Source: `brain/sleep.py:22-63`)
- **`should_being_stay_asleep(daemon)`** -- Checks if wake time is still in the future. Used to respect the being's sleep choice when a client connects. (Source: `brain/sleep.py:308-326`)

## Sleep Duration System

| Hours | Label | Consolidate | Ratio |
|-------|-------|-------------|-------|
| 1 | nap | No | 10% |
| 4 | short | Yes | 40% |
| 6 | normal | Yes | 60% |
| 8 | long | Yes | 80% |
| 10 | deep | Yes | 100% |

Ratio determines what portion of thoughts get consolidated. Relationship/thread updates only occur for 4h+ sleep.

## Dependencies

`brain.consolidation`, `config` (sleep parameters), `core.queue` (DaemonState)

See also: [brain_consolidation](brain_consolidation.md), [concept: sleep-and-dreaming](../concepts/sleep_and_dreaming.md)
