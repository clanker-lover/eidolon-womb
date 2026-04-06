# brain/actions.py

Action tag parser, execution loop, and intent detection.

## What It Does

Parses `[UPPER_TAG:argument]` patterns from model output, dispatches to tool handlers, feeds results back for continuation (up to 3 rounds). Also contains extensive intent detection for notifications, exploration, and thread interactions when the model can't produce proper tag syntax.

## Key Functions

- **`resolve_actions_async(text, generate_fn, messages, ...)`** -- Main async resolution loop. Parses tags, executes tools, re-generates up to `MAX_ACTION_ROUNDS` (3). Falls back to intent detection for notifications and exploration. (Source: `brain/actions.py:820-979`)
- **`resolve_actions_sync(text, generate_fn, messages)`** -- Blocking version for standalone chat client. (Source: `brain/actions.py:982-1017`)
- **`parse_first_tag(text)`** -- Returns `(tag_name, argument, start, end)` for first recognized tag. (Source: `brain/actions.py:775-786`)
- **`execute_tag(tag_name, argument)`** -- Dispatches to `TOOL_REGISTRY`. (Source: `brain/actions.py:789-807`)
- **`extract_notification_intent(text)`** -- Detects natural-language desire to notify Human. Filters meta-narrative and exploration actions. (Source: `brain/actions.py:224-291`)
- **`extract_exploration_intent(text)`** -- Detects desire to read news, browse filesystem, or research topics. Maps topics to RSS feeds or Wikipedia URLs. (Source: `brain/actions.py:703-772`)
- **`extract_thread_intent(text, known_names)`** -- Detects desire to message, respond to, or search threads. (Source: `brain/actions.py:100-181`)

## Design

The intent detection system is large (~500 lines of phrase lists and extraction logic) because small models express desires in natural language rather than formatted tags. The system "meets the being halfway" by detecting intent patterns and fulfilling them.

All intent-detected actions are gated through `binary_gate()` to confirm before executing.

## Dependencies

`tools` (TOOL_REGISTRY, RSS_FEEDS), `brain.intent` (binary_gate)

See also: [concept: binary-intent-system](../concepts/binary_intent_system.md), [interface_tools](interface_tools.md)
