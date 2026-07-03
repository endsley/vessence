"""Pure helpers for update_idle_state.py."""

from __future__ import annotations

import time
from pathlib import Path


def idle_state_payload(active_ts: float) -> dict:
    return {
        "last_active_ts": active_ts,
        "last_active_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(active_ts)),
    }


def atomic_tmp_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tmp")


def claude_code_activity_path(idle_state_file: str | Path) -> Path:
    return Path(idle_state_file).parent / "claude_code_activity.json"
