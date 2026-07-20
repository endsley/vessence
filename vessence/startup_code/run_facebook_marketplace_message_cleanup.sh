#!/usr/bin/env bash
# Daily Facebook Marketplace Messenger cleanup.
#
# Uses Chieh's persistent Playwright Chromium profile and deletes only chats
# classified as sold/gone or stale after the configured retention window.
set -euo pipefail

if [[ "${FB_MARKETPLACE_MESSAGE_HEADFUL_DEBUG:-}" != "1" ]]; then
  unset DISPLAY WAYLAND_DISPLAY
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env
PYTHON="$PYTHON_BIN"
MAX_DELETE="${FB_MARKETPLACE_MESSAGE_MAX_DELETE:-1000}"
STALE_DAYS="${FB_MARKETPLACE_MESSAGE_STALE_DAYS:-21}"

LOG_DIR="$VESSENCE_DATA_HOME/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/facebook_marketplace_message_cleanup.log"

cd "$VESSENCE_HOME"
export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
export PYTHONPATH="$VESSENCE_HOME:${PYTHONPATH:-}"

echo "=== $(date -Iseconds) facebook marketplace message cleanup start ===" >>"$LOG"
"$PYTHON" "$VESSENCE_HOME/agent_skills/facebook_marketplace_message_cleanup.py" \
  --delete \
  --include-protected \
  --max-delete "$MAX_DELETE" \
  --stale-days "$STALE_DAYS" \
  >>"$LOG" 2>&1
echo "=== $(date -Iseconds) facebook marketplace message cleanup done ===" >>"$LOG"
