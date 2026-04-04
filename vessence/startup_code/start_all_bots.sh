#!/bin/bash
# start_all_bots.sh - Unified launcher for Amber and Jane
# Optimized for systemd usage with absolute paths

HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
AMBIENT_BASE="${AMBIENT_BASE:-$HOME_DIR/ambient}"

DEFAULT_VESSENCE_HOME="$AMBIENT_BASE/vessence"
if [ ! -d "$DEFAULT_VESSENCE_HOME" ] && [ -d "/home/chieh/vessence" ]; then
    DEFAULT_VESSENCE_HOME="/home/chieh/vessence"
fi
VESSENCE_HOME="${VESSENCE_HOME:-$DEFAULT_VESSENCE_HOME}"

DEFAULT_VESSENCE_DATA_HOME="$AMBIENT_BASE/vessence-data"
if [ ! -d "$DEFAULT_VESSENCE_DATA_HOME" ] && [ -d "/home/chieh/vessence-data" ]; then
    DEFAULT_VESSENCE_DATA_HOME="/home/chieh/vessence-data"
fi
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$DEFAULT_VESSENCE_DATA_HOME}"

DEFAULT_VAULT_HOME="$AMBIENT_BASE/vault"
if [ ! -d "$DEFAULT_VAULT_HOME" ] && [ -d "/home/chieh/vault" ]; then
    DEFAULT_VAULT_HOME="/home/chieh/vault"
fi
VAULT_HOME="${VAULT_HOME:-$DEFAULT_VAULT_HOME}"

export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
export AMBIENT_HOME="${AMBIENT_HOME:-$VESSENCE_DATA_HOME}"
DEFAULT_VENV_BIN="$HOME_DIR/google-adk-env/adk-venv/bin"
if [ ! -x "$DEFAULT_VENV_BIN/python" ] && [ -x "/home/chieh/google-adk-env/adk-venv/bin/python" ]; then
    DEFAULT_VENV_BIN="/home/chieh/google-adk-env/adk-venv/bin"
fi
VENV_BIN="${VENV_BIN:-$DEFAULT_VENV_BIN}"
mkdir -p "$VESSENCE_DATA_HOME/logs/Amber_log" "$VESSENCE_DATA_HOME/logs/Jane_log" "$VESSENCE_DATA_HOME/logs/System_log"

# 1. Cleanup existing processes (More aggressive)
echo "Cleaning up existing bot processes..."
pkill -9 -f "adk web" || true
pkill -9 -f "discord_bridge.py" || true
pkill -9 -f "bridge.py" || true

# Also kill anything on port 8000 just in case
if command -v fuser > /dev/null; then
    fuser -k 8000/tcp || true
fi
sleep 2

# 2. Start Amber ADK Server (Brain)
echo "Starting Amber Brain..."
cd "$VESSENCE_HOME"
nohup $VENV_BIN/adk web --port 8000 "$VESSENCE_HOME" > "$VESSENCE_DATA_HOME/logs/Amber_log/server.log" 2>&1 &

# Wait for ADK server to be ready
echo "Waiting for ADK server..."
for i in {1..30}; do
    if $VENV_BIN/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/list-apps')" > /dev/null 2>&1; then
        echo "ADK server is UP."
        break
    fi
    sleep 1
done

# 3. Start Bridges in Parallel
echo "Starting Amber and Jane Bridges in parallel..."

# Start Amber Bridge in background
cd "$VESSENCE_HOME"
nohup $VENV_BIN/python jane/discord_bridge.py > "$VESSENCE_DATA_HOME/logs/Amber_log/bridge.log" 2>&1 &
AMBER_BRIDGE_PID=$!

# Start Jane Bridge in background
cd "$HOME_DIR/gemini_cli_bridge"
nohup $VENV_BIN/python bridge.py > "$VESSENCE_DATA_HOME/logs/Jane_log/bridge.log" 2>&1 &
JANE_BRIDGE_PID=$!

echo "All bots are starting up. Amber Bridge PID: $AMBER_BRIDGE_PID, Jane Bridge PID: $JANE_BRIDGE_PID"
echo "Check $VESSENCE_DATA_HOME/logs/System_log/start.log for overall status."
