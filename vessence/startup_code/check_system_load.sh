#!/bin/bash
# Claude Code PreToolUse hook — checks system load before Bash/Agent calls
# Output is injected into Jane's context so she adjusts concurrency accordingly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"

"$PYTHON_BIN" "$VESSENCE_HOME/agent_skills/system_load.py" --oneline 2>/dev/null
