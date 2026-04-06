# Backward-Compatibility Stubs

Three top-level files exist as backward-compat stubs after module extraction.

## config.py
Re-exports `core.config` via `from core.config import *`. (Source: `config.py`)

## presence.py
Swaps `sys.modules[__name__]` to `interface.presence`. Re-exports `get_presence_status`, `get_human_status`, `get_pending_replies`, `is_human_away` for mypy. (Source: `presence.py`)

## tools.py
Swaps `sys.modules[__name__]` to `interface.tools`. Re-exports `TOOL_REGISTRY`, `RSS_FEEDS`, `tool_fetch_webpage`, `tool_fetch_rss`, `fire_notify_send` for mypy. (Source: `tools.py`)

## Design Pattern

The `sys.modules` swap pattern makes the old import path transparent -- `from tools import X` resolves to `interface.tools.X` at runtime. The explicit re-exports satisfy mypy's static analysis since the swap is invisible to type checkers.

See also: [core_config](core_config.md), [interface_presence](interface_presence.md), [interface_tools](interface_tools.md)
