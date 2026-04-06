# Dependencies

All external libraries used by Eidolon Womb.

## Python Libraries (requirements.txt)

| Library | Version | Purpose |
|---------|---------|---------|
| `ollama` | >= 0.4.0 | LLM inference and embeddings via local Ollama server |
| `rank_bm25` | >= 0.2.2 | BM25Okapi keyword scoring for hybrid memory retrieval |
| `streamlit` | >= 1.40.0 | Web dashboard framework |
| `streamlit-autorefresh` | >= 1.0.1 | Dashboard auto-refresh component |
| `trafilatura` | >= 1.6.0 | Web content extraction for FETCH_WEBPAGE tool |

(Source: `requirements.txt`)

## Optional Libraries

| Library | Purpose | Imported |
|---------|---------|----------|
| `feedparser` | RSS feed parsing for FETCH_RSS tool | Lazy import in `interface/tools.py:133` |

## System Tools (Linux)

| Tool | Package | Purpose |
|------|---------|---------|
| `xdotool` | xdotool | Active window title detection |
| `xprintidle` | xprintidle | User idle time measurement |
| `loginctl` | systemd | Screen lock detection |
| `notify-send` | libnotify-bin | Desktop notifications |
| `paplay` | pulseaudio-utils | Notification sound playback |

(Source: `interface/presence.py:1-7`, `interface/tools.py:190-203`)

## Infrastructure

| Component | Purpose |
|-----------|---------|
| Ollama server | Local LLM inference (must be running) |
| Python 3.10+ | Runtime (3.12 in dev) |
| SQLite | Embedding cache (via stdlib sqlite3) |

(Source: `README.md:82-86`, `CLAUDE.md:57`)
