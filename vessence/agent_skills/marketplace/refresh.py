"""Background harvester+summarizer runner with a file-based status marker.

The UI's "pull now" button calls an HTTP endpoint which spawns this module
as a subprocess. Because Playwright can take several minutes, we run
asynchronously: the endpoint returns immediately, and the UI polls
``refresh_status.json`` to know when the pull finished.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
import traceback
from pathlib import Path

from . import config as _cfg
from . import harvester as _harv
from . import summarize as _sum

logger = logging.getLogger(__name__)


def _status_path(search_name: str) -> Path:
    return _cfg.search_data_dir(search_name) / "refresh_status.json"


def _write_status(search_name: str, **fields) -> None:
    p = _status_path(search_name)
    try:
        current = json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        current = {}
    current.update(fields)
    p.write_text(json.dumps(current, indent=2))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError):
        return False


def get_status(search_name: str) -> dict:
    p = _status_path(search_name)
    if not p.exists():
        return {"state": "idle"}
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"state": "idle"}
    # If the runner crashed without writing an exit state, report idle_stale
    # so the UI doesn't spin forever.
    if d.get("state") == "running":
        pid = d.get("pid")
        if isinstance(pid, int) and not _pid_alive(pid):
            d["state"] = "idle_stale"
    return d


def run(search_name: str) -> None:
    """Run harvester + summarizer, writing progress to refresh_status.json."""
    _write_status(search_name,
                  state="running",
                  started_at=dt.datetime.now().isoformat(timespec="seconds"),
                  pid=os.getpid(),
                  error=None)
    try:
        logger.info("pull starting for %s", search_name)
        _harv.harvest(search_name)
        _sum.summarize(search_name)
        _write_status(search_name,
                      state="idle",
                      finished_at=dt.datetime.now().isoformat(timespec="seconds"),
                      error=None)
        logger.info("pull finished for %s", search_name)
    except Exception as e:
        logger.exception("pull failed for %s", search_name)
        _write_status(search_name,
                      state="error",
                      finished_at=dt.datetime.now().isoformat(timespec="seconds"),
                      error=f"{type(e).__name__}: {e}",
                      traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("usage: python -m agent_skills.marketplace.refresh <search_name>")
        sys.exit(1)
    run(sys.argv[1])
