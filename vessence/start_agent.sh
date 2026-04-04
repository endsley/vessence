#!/bin/bash
# start_agent.sh
set -e

HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
AMBIENT_BASE="${AMBIENT_BASE:-$HOME_DIR/ambient}"
VESSENCE_HOME="${VESSENCE_HOME:-/home/chieh/vessence}"
VESSENCE_HOME="${VESSENCE_HOME:-$AMBIENT_BASE/vessence}"
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$AMBIENT_BASE/vessence-data}"
VAULT_HOME="${VAULT_HOME:-$AMBIENT_BASE/vault}"
export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
export AMBIENT_HOME="${AMBIENT_HOME:-$VESSENCE_DATA_HOME}"
mkdir -p "$VESSENCE_DATA_HOME/logs/Amber_log"

# Load environment
export ADK_SESSION_STALE_CHECK=0
source /home/chieh/google-adk-env/adk-venv/bin/activate
cd "$VESSENCE_HOME"

# Kill existing
pkill -9 -f "adk api_server" || true
pkill -9 -f "adk web" || true
pkill -9 -f "discord_bridge.py" || true

# Start Server
echo "Starting ADK Server with adk web..."
# adk web expects a directory of agents. Each subdirectory is an agent.
# Our agent is in the Vessence code root.
nohup adk web --session_service_uri "memory://" --port 8000 "$VESSENCE_HOME" > "$VESSENCE_DATA_HOME/logs/Amber_log/server.log" 2>&1 &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server on port 8000..."
for i in {1..30}; do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/list-apps')" > /dev/null 2>&1; then
        echo "Server is UP."
        break
    fi
    sleep 1
done

# Start Bridge
echo "Starting Discord Bridge..."
nohup python jane/discord_bridge.py > "$VESSENCE_DATA_HOME/logs/Amber_log/bridge.log" 2>&1 &
BRIDGE_PID=$!

echo "Agent and Bridge started. Server PID: $SERVER_PID, Bridge PID: $BRIDGE_PID"
