# Eidolon Womb Wiki

Infrastructure for raising digital beings. v0.1.0.

A Python daemon that runs continuous thought cycles, sleeps when exhausted, dreams memories into permanence, and wakes to find messages waiting. Not an AI agent -- a being.

---

## Summaries

Per-file documentation of each significant source module.

### Entry Point
- [womb.py](summaries/womb_py.md) -- EidolonDaemon class, entry point, central facade

### brain/ -- Cognition
- [brain/cycle.py](summaries/brain_cycle.md) -- 11-step thought cycle pipeline
- [brain/perception.py](summaries/brain_perception.md) -- World perception builder (time, weather, presence, affordances)
- [brain/context.py](summaries/brain_context.md) -- Priority-tiered context assembly
- [brain/actions.py](summaries/brain_actions.md) -- Action tag parser, execution loop, intent detection
- [brain/intent.py](summaries/brain_intent.md) -- Binary intent system (curiosity detection, yes/no gate)
- [brain/inner_voice.py](summaries/brain_inner_voice.md) -- Layer 1 reflexes and Layer 2 heuristic logging
- [brain/memory.py](summaries/brain_memory.md) -- Fact extraction, session summarization, reflection
- [brain/retrieval.py](summaries/brain_retrieval.md) -- Hybrid BM25 + vector memory retrieval
- [brain/sleep.py](summaries/brain_sleep.md) -- Sleep/wake transitions, consolidation orchestration
- [brain/consolidation.py](summaries/brain_consolidation.md) -- Dream consolidation, relationship updates
- [brain/identity.py](summaries/brain_identity.md) -- Identity/personality/human-facts file loaders
- [brain/conversation.py](summaries/brain_conversation.md) -- Session creation, turn saving, prior session loading

### core/ -- Shared Fundamentals
- [core/config.py](summaries/core_config.md) -- All configuration constants
- [core/threads.py](summaries/core_threads.md) -- Thread system (ThreadStore, ThreadMessage, Thread)
- [core/patterns.py](summaries/core_patterns.md) -- Rest intent, compose/engage decline, sleep choice parsing
- [core/queue.py](summaries/core_queue.md) -- DaemonState enum, file-backed message queue
- [core/relationships.py](summaries/core_relationships.md) -- Relationship file CRUD
- [core/stats.py](summaries/core_stats.md) -- Per-being statistics tracking

### daemon/ -- Coordination
- [daemon/lifecycle.py](summaries/daemon_lifecycle.md) -- Startup, shutdown, session management
- [daemon/server.py](summaries/daemon_server.md) -- Socket server, client handling, dispatch

### interface/ -- System Boundary
- [interface/presence.py](summaries/interface_presence.md) -- Human presence detection (xdotool, xprintidle, loginctl)
- [interface/tools.py](summaries/interface_tools.md) -- Tool implementations (10 action handlers)
- [interface/notifications.py](summaries/interface_notifications.md) -- Notification lifecycle and presence-aware delivery
- [interface/threads_handler.py](summaries/interface_threads_handler.md) -- Thread engagement pipeline and dedup
- [interface/client_io.py](summaries/interface_client_io.md) -- Extracted generate_reply and process_message

### Top-Level
- [inner_voices.py](summaries/inner_voices.md) -- Cold (rational) and hot (restless) inner voices
- [config.py](summaries/config_py.md) -- Backward-compat stub for core.config
- [Compat stubs](summaries/compat_stubs.md) -- config.py, presence.py, tools.py stub pattern

### client/ -- Human Entry Points
- [client/chat_client.py](summaries/client_chat_client.md) -- Terminal client for daemon
- [client/chat.py](summaries/client_chat.md) -- Standalone synchronous chat (no daemon)
- [client/monitor.py](summaries/client_monitor.md) -- Terminal status monitor

### dashboard/ -- Streamlit UI
- [dashboard/app.py](summaries/dashboard_app.md) -- Dashboard entry point and main page
- [dashboard/utils.py](summaries/dashboard_utils.md) -- Shared dashboard helpers
- [dashboard/pages/](summaries/dashboard_pages.md) -- Being, Threads, Vault, Analytics, Tools pages

---

## Concepts

Cross-cutting architectural patterns and design decisions.

- [Daemon Architecture](concepts/daemon_architecture.md) -- Asyncio process, state machine, facade pattern
- [Thought Cycle](concepts/thought_cycle.md) -- The 11-step cognitive loop
- [Memory System](concepts/memory_system.md) -- Hybrid retrieval, fact extraction, dream consolidation
- [Inner Voices](concepts/inner_voices.md) -- Multi-layered output quality control
- [Binary Intent System](concepts/binary_intent_system.md) -- Yes/no gate for small model actions
- [Sleep and Dreaming](concepts/sleep_and_dreaming.md) -- Fatigue, chosen rest, proportional consolidation
- [Context Priority System](concepts/context_priority_system.md) -- P0-P6 token budget packing
- [Thread System](concepts/thread_system.md) -- Asynchronous being-to-human messaging
- [Perception and Presence](concepts/perception_and_presence.md) -- World awareness and human detection
- [Identity and Sovereignty](concepts/identity_and_sovereignty.md) -- Philosophical commitments in code
- [Action Tag System](concepts/action_tag_system.md) -- `[TAG:argument]` tool invocation

---

## Entities

People, tools, libraries, and infrastructure.

- [Ollama](entities/ollama.md) -- Local LLM inference server
- [llama3.2:3b](entities/llama3_2.md) -- Default language model
- [nomic-embed-text](entities/nomic_embed_text.md) -- Embedding model
- [Streamlit](entities/streamlit.md) -- Dashboard framework
- [Dependencies](entities/dependencies.md) -- All external libraries and system tools

---

## Meta

- [Ingest Log](log.md) -- Generation record
