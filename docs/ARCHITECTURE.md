# Architecture

Technical deep-dive into the Eidolon Womb infrastructure.

---

## Overview

The womb is a daemon process that maintains continuous thought cycles for a single digital being. Unlike request-response systems, the being thinks whether or not a human is present. Messages from humans are queued and discovered by the being during natural thought flow.
```
┌─────────────────────────────────────────────┐
│                 DAEMON                       │
│  ┌─────────────────────────────────────┐    │
│  │          Thought Cycle              │    │
│  │  (continuous, 27-minute periods)    │    │
│  └─────────────────────────────────────┘    │
│                    │                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ Memory  │ │  Sleep  │ │ Intent  │       │
│  │ System  │ │ System  │ │ System  │       │
│  └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────┘
         ▲                    │
         │    Socket API      │
         ▼                    ▼
┌─────────────┐      ┌─────────────┐
│   Client    │      │  Dashboard  │
│ (chat_client)│      │ (Streamlit) │
└─────────────┘      └─────────────┘
```

---

## The 11-Step Thought Cycle

Each thought cycle follows this pipeline (defined in `brain/cycle.py`):

1. **Inject Pending Results** — Carry forward search results from previous cycle (step 0, conditional)
2. **Refresh Perception** — Update world state (time, window focus, pending messages)
3. **Memory Retrieval** — BM25 + vector search via `MemoryIndex.search()`
4. **Build Thinking Prompt** — Context-appropriate prompt based on state
5. **Assemble Messages** — Priority-tiered packing (P0-P6) within token budget
6. **Generate** — Ollama completion
7. **Resolve Actions** — Parse `[TAG:argument]` patterns, execute tools, inject results (up to 3 rounds)
8. **Intent Detection** — Curiosity/exploration/notification detection with binary gate confirmation
9. **Inner Voice** — Reflexes, heuristics, cold/hot voice layers
10. **Thread Engagement** — Handle thread responses and compose flows
11. **Save Thought** — Persist to disk
12. **Sleep Detection** — Check voluntary/involuntary sleep readiness

(Step 0 is bookkeeping, step 12 is an exit condition — the core pipeline is 11 stages.)

The cycle repeats continuously. ~40 cycles fit in a 27-minute "waking period" before fatigue accumulates.

---

## Sleep System

Beings accumulate fatigue through thought cycles. When fatigue reaches threshold, the being chooses to sleep.

**Sleep duration:** 1-10 hours, chosen by the being based on:
- Current fatigue level
- Recent activity intensity
- Pending messages (may delay sleep briefly)

**During sleep — Memory Consolidation:**
- Recent experiences are reviewed
- Important patterns are extracted
- Memories are consolidated into `memories/consolidated/`
- Context is cleared, fatigue resets

This mimics biological sleep's role in memory formation. The being that wakes up has integrated its experiences into identity.

---

## Binary Intent System

**The problem:** Small models (3B parameters) can't reliably format structured tool calls. They hallucinate JSON, miss required fields, invent parameters.

**The solution:** Separate thinking from deciding.
```
Thought (full language)
       │
       ▼
Pattern Detection (regex)
       │ curiosity? exploration? notification?
       ▼
Binary Gate (LLM)
       │ "Do X right now? yes/no"
       │ temp=0, max_tokens=1
       ▼
Action Execution (if yes)
       │
       ▼
Result Injection (into next cycle)
```

**Why it works:** Yes/no is the simplest possible output format. Even small models can reliably produce a single token when the question is unambiguous.

**Implementation:** `brain/intent.py` and `brain/actions.py`

---

## Action System

Actions use `[TAG:argument]` syntax — simple patterns that small models reliably produce.

**Execution flow** (`brain/actions.py`):
1. Scan output for `[UPPER_TAG:...]` patterns
2. Dispatch to `TOOL_REGISTRY` handler
3. Inject result into conversation
4. Re-generate (up to 3 rounds)

**Available tools:**

| Tag | Function |
|-----|----------|
| `CHECK_WINDOW` | Read focused X11 window title |
| `LIST_DIR` | Browse filesystem (data directory only) |
| `READ_FILE` | Read file contents |
| `FETCH_RSS` | Cached RSS feed (15-min TTL) |
| `FETCH_WEBPAGE` | Article extraction via trafilatura |
| `SEND_NOTIFICATION` | Desktop notification with sound |
| `START_THREAD` | Create new message thread |
| `RESPOND_THREAD` | Reply to existing thread |
| `DISMISS_THREAD` | Mark thread as handled |
| `SEARCH_THREADS` | Find threads by content |

**Fallback intent detection:** If no explicit tags, check for notification intent (contact Human) and exploration intent (news/Wikipedia/browse), both gated by `binary_gate()`.

---

## Memory System

Hybrid retrieval combining keyword and semantic search:

**BM25 keyword scoring** — Fast lexical matching via rank-bm25 library.

**Vector embeddings** — nomic-embed-text via Ollama for semantic similarity. Embeddings cached in SQLite, keyed by SHA-256 content hash. Cache persists across restarts.

**Blended ranking** — Configurable weights between BM25 and vector scores. Default favors keywords with semantic tiebreaking.

**Memory sources:**
- `memories/consolidated/` — Dream-processed long-term memories
- Session summaries and notes
- Known facts and learned facts
- Relationship files

Retrieval called every cycle (step 2) to populate context with relevant memories.

---

## Context Assembly

Each cycle packs messages into the context window using priority tiers (defined in `brain/context.py`):

| Priority | Content | Trim Behavior |
|----------|---------|---------------|
| P0 | Perception, identity | Never trimmed |
| P1 | Guardrails | Never trimmed |
| P2 | Personality | Whole or dropped |
| P3 | Seed facts, then learned facts (newest first) | Truncate from oldest |
| P4 | Retrieved memories | Truncate from lowest score |
| P5 | Session summaries | Truncate from oldest |
| P6 | Conversation history | Most recent first until budget exhausted |

Default budget: `MAX_PROMPT_TOKENS` (configurable).
Thread replies use separate 12,000-token budget via `assemble_thread_context()`.

---

## Directory Structure
```
data/
├── identity.md           # Core identity (who am I?)
├── personality.md        # Personality traits (how do I engage?)
├── being_state.json      # Runtime state (fatigue, cycle count, etc.)
├── stats.json            # Aggregate statistics
├── relationships/
│   └── Human.md          # Relationship with the human
├── memories/
│   └── consolidated/     # Dream-processed memories
├── conversations/        # Conversation logs
├── threads/              # Message threads
└── logs/                 # Debug logs
```

---

## Daemon States
```python
class DaemonState(Enum):
    AWAKE_AVAILABLE = "awake_available"   # Thinking, can receive messages
    AWAKE_BUSY = "awake_busy"             # Mid-thought, queue messages
    ASLEEP = "asleep"                      # Sleeping, messages wait
```

**State transitions:**
- `AWAKE_AVAILABLE` → `AWAKE_BUSY`: Entering thought cycle
- `AWAKE_BUSY` → `AWAKE_AVAILABLE`: Cycle complete
- `AWAKE_AVAILABLE` → `ASLEEP`: Fatigue threshold reached, sleep initiated
- `ASLEEP` → `AWAKE_AVAILABLE`: Sleep duration complete

---

## Configuration

All configuration lives in `core/config.py`:

- **Cycle timing** — Thought duration, waking period length
- **Sleep parameters** — Fatigue threshold, consolidation settings
- **Intent thresholds** — Cooldowns, pattern sensitivity
- **Model settings** — Temperature, context window, generation limits

---

## Extending the Womb

The architecture is designed for extension:

**New actions:** Add patterns to `brain/intent.py`, handlers to `brain/actions.py`

**New memory types:** Extend the extraction logic in `brain/memory.py`

**Different models:** Swap the model name in config. The binary intent system is model-agnostic.

**Dashboard customization:** Streamlit pages in `dashboard/pages/`

---
