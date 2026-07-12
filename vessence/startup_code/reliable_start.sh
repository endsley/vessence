#!/bin/bash
# reliable_start.sh - Background launcher for Jane's gemini_cli_bridge
#
# NOTE (v0.1.71): Amber/discord_bridge startup was removed. The Amber ADK
# server (adk web --port 8000) and jane/discord_bridge.py were retired when
# amber/ was deleted. Jane runs via systemd (jane-web.service) and this
# script only starts the gemini CLI bridge.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env

rm -f /tmp/jane_bridge.lock
bash "$SCRIPT_DIR/start_all_bots.sh"
