#!/bin/bash
# reliable_start.sh - Background launcher for Jane's gemini_cli_bridge
#
# NOTE (v0.1.71): Amber/discord_bridge startup was removed. The Amber ADK
# server (adk web --port 8000) and jane/discord_bridge.py were retired when
# amber/ was deleted. Jane runs via systemd (jane-web.service) and this
# script only starts the gemini CLI bridge.
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
mkdir -p "$VESSENCE_DATA_HOME/logs/Jane_log"

echo "Cleaning up existing bridge processes..."
pkill -9 -f "gemini_cli_bridge/bridge.py" || true
rm -f /tmp/jane_bridge.lock
sleep 2

# Start Jane Bridge (gemini CLI)
echo "Starting Jane Bridge..."
cd "$HOME_DIR/gemini_cli_bridge"
nohup $VENV_BIN/python bridge.py > "$VESSENCE_DATA_HOME/logs/Jane_log/bridge.log" 2>&1 &

echo "Jane bridge initiated. Check logs for status."
