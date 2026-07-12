#!/bin/bash
# start_all_bots.sh - Unified launcher for Jane's bridge(s).
#
# NOTE (v0.1.71): Amber ADK server + discord_bridge startup was removed.
# amber/ directory, amber-brain.service, and jane/discord_bridge.py were
# retired when Discord integration was disabled. Jane runs via systemd
# (jane-web.service); this script only starts the gemini CLI bridge.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env
mkdir -p "$VESSENCE_DATA_HOME/logs/Jane_log" "$VESSENCE_DATA_HOME/logs/System_log"

# Cleanup existing bridge processes
echo "Cleaning up existing bridge processes..."
pkill -9 -f "gemini_cli_bridge/bridge.py" || true
sleep 2

# Start Jane Bridge (gemini CLI)
echo "Starting Jane Bridge..."
cd "$HOME_DIR/gemini_cli_bridge"
nohup $VENV_BIN/python bridge.py > "$VESSENCE_DATA_HOME/logs/Jane_log/bridge.log" 2>&1 &
JANE_BRIDGE_PID=$!

echo "Jane Bridge started. PID: $JANE_BRIDGE_PID"
echo "Check $VESSENCE_DATA_HOME/logs/System_log/start.log for overall status."
