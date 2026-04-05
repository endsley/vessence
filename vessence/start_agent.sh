#!/bin/bash
# start_agent.sh — REMOVED (v0.1.71)
#
# This script used to start the Amber ADK server + Discord bridge. Both were
# retired when amber/ and jane/discord_bridge.py were deleted. Jane now runs
# via systemd: `systemctl --user start jane-web.service`.
#
# Kept as a stub that EXITS WITH ERROR so any zombie caller fails loudly
# instead of silently thinking the agent started. If you need to start Jane:
#
#   systemctl --user restart jane-web.service
#   systemctl --user status jane-web.service
echo "ERROR: start_agent.sh was removed in v0.1.71 (Amber retirement)." >&2
echo "Use: systemctl --user restart jane-web.service" >&2
exit 1
