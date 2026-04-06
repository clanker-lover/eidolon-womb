# Streamlit

Web-based dashboard framework used for the being's monitoring UI.

## Role in Eidolon Womb

Streamlit powers the optional dashboard (launched by `./start.sh` or `streamlit run dashboard/app.py`). It provides a web UI at http://localhost:8501 for monitoring the being, browsing threads, viewing memories, and interacting.

## Pages

- **Dashboard** (`dashboard/app.py`) -- Main status, control buttons, quick stats
- **Being** (`dashboard/pages/1_being.py`) -- Identity, personality, live status
- **Threads** (`dashboard/pages/2_threads.py`) -- Thread list, message view, compose
- **Vault** (`dashboard/pages/3_vault.py`) -- Historical data file browser
- **Analytics** (`dashboard/pages/4_analytics.py`) -- Being statistics
- **Tools** (`dashboard/pages/5_tools.py`) -- Tool use stats and log viewer

## Dependencies

- `streamlit>=1.40.0` (Source: `requirements.txt:3`)
- `streamlit-autorefresh>=1.0.1` for 15-second auto-refresh (Source: `requirements.txt:4`)

## Communication

Dashboard communicates with the daemon via raw TCP sockets (not HTTP). Uses `peek` protocol for status, `thread_reply` for being responses, `command` for state changes. (Source: `dashboard/utils.py:35-115`)
