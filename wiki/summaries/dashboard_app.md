# dashboard/app.py

Streamlit dashboard entry point and main page.

## What It Does

Main dashboard page with sidebar (daemon status, settings) and two-column layout showing being status, control buttons, and quick stats. Auto-refreshes every 15 seconds via `streamlit-autorefresh`.

## Features

- **Sidebar**: Daemon connection status, being name/status indicator, user name settings (persisted to `data/user_config.json`).
- **Unread notifications**: Scans threads for unread messages, displays count and previews with dismiss button.
- **Being status**: Name, current mode (sleeping/thinking/idle with countdown), fatigue progress bar, session thought count.
- **Control buttons**: Normal/Stasis toggle -- sends commands to daemon via socket.
- **Quick stats**: Conversation count, learned facts count, consolidation count.

## Dependencies

`streamlit`, `streamlit_autorefresh`, `dashboard/utils.py`

See also: [dashboard_utils](dashboard_utils.md), [dashboard_pages](dashboard_pages.md)
