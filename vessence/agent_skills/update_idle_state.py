#!/usr/bin/env python3
"""
update_idle_state.py — Records the user's last active timestamp for idle detection.
Called by UserPromptSubmit hook on every Claude Code prompt.
Writes to:
  - idle_state.json: shared signal used by the prompt queue runner. Note: Jane web
    also writes here on every API call, so this signal covers ANY user activity.
  - claude_code_activity.json: Claude Code-only signal used by the Jane archival
    sweep (jane_proxy._read_global_idle_ts) to gate archival on CC activity
    specifically — Jane web traffic must NOT touch this file.
Both files are written atomically (write to .tmp, rename).
"""
import json
import os
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills.idle_state_helpers import (
    atomic_tmp_path as _atomic_tmp_path,
    claude_code_activity_path as _claude_code_activity_path,
    idle_state_payload as _idle_state_payload,
)
from jane.config import IDLE_STATE_PATH

IDLE_STATE_FILE = IDLE_STATE_PATH
CC_ACTIVITY_FILE = _claude_code_activity_path(IDLE_STATE_FILE)


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _atomic_tmp_path(path)
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, path)


def main():
    state = _idle_state_payload(time.time())
    _atomic_write(Path(IDLE_STATE_FILE), state)
    _atomic_write(CC_ACTIVITY_FILE, state)


if __name__ == "__main__":
    main()
