#!/usr/bin/env python3
"""
update_idle_state.py — Records the user's last active timestamp for idle detection.
Called by UserPromptSubmit hook on every Claude Code prompt.
Writes to idle_state.json (used by check_continuation.py).
"""
import json
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import IDLE_STATE_PATH

IDLE_STATE_FILE = IDLE_STATE_PATH


def main():
    state = {
        "last_active_ts": time.time(),
        "last_active_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    Path(IDLE_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(IDLE_STATE_FILE, "w") as f:
        json.dump(state, f)


if __name__ == "__main__":
    main()
