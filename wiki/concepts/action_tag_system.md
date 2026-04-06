# Action Tag System

How the being interacts with the world: `[TAG:argument]` syntax and tool execution.

## FACTS

- Actions use `[UPPER_TAG:argument]` syntax -- simple bracket-enclosed patterns that small models can reliably produce. No JSON, no structured output. (Source: `brain/actions.py:1-5`)
- Tag regex: `[A-Z][A-Z0-9_]+` optionally followed by `:argument`. Won't match `[PERCEPTION -- ...]`, `[Memory]`, markdown links, or lowercase text. (Source: `brain/actions.py:23`)
- Execution loop: parse first tag, execute handler, inject result as `[Tool result - TAG]...[End tool result]`, re-generate, repeat up to 3 rounds. (Source: `brain/actions.py:820-870`)
- 10 tools in TOOL_REGISTRY: CHECK_WINDOW, LIST_DIR, READ_FILE, FETCH_RSS, FETCH_WEBPAGE, SEND_NOTIFICATION, START_THREAD, RESPOND_THREAD, DISMISS_THREAD, SEARCH_THREADS. (Source: `interface/tools.py:363-374`)
- Intent detection fallbacks run when no explicit tags are found: notification intent (16 phrases) and exploration intent (news/filesystem/topic). Both gated by binary_gate(). (Source: `brain/actions.py:875-978`)
- RSS feeds cached 15 minutes. Five feeds: AP News, Reuters, Ars Technica, Lifehacker, Nature. (Source: `interface/tools.py:25-31`)
- Webpage extraction via trafilatura library, capped at 6000 chars. (Source: `interface/tools.py:164-188`)
- Notifications route through daemon's queue system -- they fire via `notify-send` when Human returns to his PC. (Source: `interface/tools.py:207-218`)
- Thread tools support short ID prefix matching (8 chars shown in perception). (Source: `interface/tools.py:235-240`)

## INFERENCES

- The `[TAG:argument]` syntax was chosen for reliability over expressiveness. Small models can produce bracketed uppercase text far more reliably than JSON or function call syntax.
- The 3-round execution limit prevents infinite tool-calling loops where the model keeps producing tags.

## Cross-References

- [brain_actions](../summaries/brain_actions.md) -- Parser and execution
- [interface_tools](../summaries/interface_tools.md) -- Tool implementations
- [binary-intent-system](binary_intent_system.md) -- Fallback detection
- [thought-cycle](thought_cycle.md) -- Where actions resolve
