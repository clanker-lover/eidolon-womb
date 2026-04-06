# dashboard/pages/

Streamlit dashboard sub-pages.

## 1_being.py -- Being Profile

Displays identity, personality, live status (name, model, fatigue, thought count, active threads, consolidation count), and recent consolidation previews. (Source: `dashboard/pages/1_being.py`)

## 2_threads.py -- Threads

Two-column layout: thread list (filterable by participant and status) and selected thread view. Message display with pagination (5 most recent, load-more button). Reply form and new thread composer. Maps historical being names ("Being", "Eidolon") to current name. Marks threads as read on view. (Source: `dashboard/pages/2_threads.py`)

## 3_vault.py -- Vault

Historical data browser. Sections: Identity/Personality, Conversations, Archived Conversations, Memories, Consolidated Memories, Logs. Each file expandable with content preview. Search filter by filename. (Source: `dashboard/pages/3_vault.py`)

## 4_analytics.py -- Analytics

Displays per-being statistics: thoughts, threads created, thread replies, tool uses, last activity timestamp. (Source: `dashboard/pages/4_analytics.py`)

## 5_tools.py -- Tool Use

Tool use counter from stats. Recent log entries filtered for tool/action/tag/intent-detected/exploration keywords. (Source: `dashboard/pages/5_tools.py`)

## Dependencies

All pages import from `dashboard/utils.py`. Thread page imports `core.threads.ThreadMessage` directly.

See also: [dashboard_app](dashboard_app.md), [dashboard_utils](dashboard_utils.md)
