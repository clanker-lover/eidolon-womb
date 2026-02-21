#!/bin/bash
# Start Eidolon Womb - daemon + dashboard
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Read port from config
PORT=$(python3 -c "from core.config import DAEMON_PORT; print(DAEMON_PORT)" 2>/dev/null || echo 7777)

# GUARD: fail if port already in use
if nc -z localhost "$PORT" 2>/dev/null; then
    echo ""
    echo "ERROR: Port $PORT already in use. Another daemon may be running."
    echo "Stop it first or change DAEMON_PORT in core/config.py"
    echo ""
    exit 1
fi

# Ensure log directory exists
mkdir -p data/logs

# Start daemon in background, logs to file
python3 womb.py > data/logs/daemon.log 2>&1 &
DAEMON_PID=$!
echo $DAEMON_PID > data/.daemon.pid

# Verify our daemon process is actually running
sleep 1
if ! kill -0 "$DAEMON_PID" 2>/dev/null; then
    echo ""
    echo "ERROR: Daemon failed to start. Check data/logs/daemon.log"
    echo ""
    tail -5 data/logs/daemon.log 2>/dev/null
    rm -f data/.daemon.pid
    exit 1
fi

# Wait for daemon to be ready (socket available)
READY=0
for i in {1..15}; do
    if nc -z localhost "$PORT" 2>/dev/null; then
        READY=1
        break
    fi
    # Check process still alive while waiting
    if ! kill -0 "$DAEMON_PID" 2>/dev/null; then
        echo ""
        echo "ERROR: Daemon died during startup. Check data/logs/daemon.log"
        echo ""
        tail -10 data/logs/daemon.log 2>/dev/null
        rm -f data/.daemon.pid
        exit 1
    fi
    sleep 0.5
done

if [ "$READY" -eq 0 ]; then
    echo ""
    echo "ERROR: Daemon started but not listening on port $PORT after 7.5s."
    echo "Check data/logs/daemon.log"
    echo ""
    tail -10 data/logs/daemon.log 2>/dev/null
    exit 1
fi

echo "Daemon started (PID $DAEMON_PID, port $PORT)"

# Launch dashboard (this will open browser)
streamlit run dashboard/app.py --server.headless false
