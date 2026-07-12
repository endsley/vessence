#!/usr/bin/env bash
# Nightly marketplace refresh: harvest every saved search, then generate
# a Stage-2 LLM summary per search.
#
# Runs strictly headless — DISPLAY/WAYLAND_DISPLAY are unset before launch
# so Playwright doesn't try to attach to an X session that isn't there.
#
# Installed via crontab entry (see configs/CRON_JOBS.md §N):
#     0 2 * * * $VESSENCE_HOME/startup_code/run_marketplace_cron.sh
set -euo pipefail

# Force headless regardless of the parent env.
unset DISPLAY WAYLAND_DISPLAY

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env
PYTHON="$PYTHON_BIN"

LOG_DIR="$VESSENCE_DATA_HOME/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/marketplace_harvest.log"

cd "$VESSENCE_HOME"
export PYTHONPATH="$VESSENCE_HOME:$VESSENCE_HOME/agent_skills:${PYTHONPATH:-}"

echo "=== $(date -Iseconds) marketplace cron start ===" >>"$LOG"

# List all saved searches, then process each one. The harvester + summarizer
# each have their own per-search logging via Python's logger; we tee
# everything into the rotating log file.
SEARCHES=$("$PYTHON" -c "
import sys, json
sys.path.insert(0, 'agent_skills')
from marketplace import config as c
print(json.dumps([s['name'] for s in c.list_searches()]))
")

"$PYTHON" -c "
import json, sys
names = json.loads(sys.argv[1])
print('\\n'.join(names))
" "$SEARCHES" | while read -r name; do
  [ -z "$name" ] && continue
  echo "--- $(date -Iseconds) harvest $name ---" >>"$LOG"
  "$PYTHON" -m agent_skills.marketplace.refresh "$name" >>"$LOG" 2>&1 \
    || echo "!!! $(date -Iseconds) refresh $name FAILED (continuing)" >>"$LOG"
done

echo "=== $(date -Iseconds) marketplace cron done ===" >>"$LOG"
