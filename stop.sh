#!/bin/bash
# Stop Eidolon Womb gracefully

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "data/.daemon.pid" ]; then
    PID=$(cat data/.daemon.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Daemon stopped (PID $PID)"
    else
        echo "Daemon not running (stale PID $PID)"
    fi
    rm data/.daemon.pid
else
    echo "No PID file found — daemon may not be running"
fi
