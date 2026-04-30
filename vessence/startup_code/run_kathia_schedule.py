#!/usr/bin/env python3
"""Runner for KathiaScheduleSequence cron job.

Phase 1: trigger AI summary generation for all patients (~1 click per patient).
Wait:    30 min for AI to generate summaries.
Phase 2: extract health_concerns, recommendations, visit_summary from each modal.
Saves all data to SQLite at VESSENCE_DATA_HOME/schedule.db.

Installed cron: every 4 hours, every day. Typical run time is ~32 minutes.
This wrapper uses a non-blocking singleton lock so cron cannot overlap runs
if a previous scrape is still active.
"""
import asyncio
import fcntl
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from skills.web_sequences.kathia_schedule import KathiaScheduleSequence

DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data"))
TRACKER_PATH = DATA_HOME / "clinic_last_pull.json"
LOGS_DIR = DATA_HOME / "logs"
LOCK_PATH = LOGS_DIR / "kathia_schedule.lock"


def _acquire_singleton_lock() -> None:
    """Exit quietly if a previous clinic scrape is still running.

    Cron fires this wrapper every 4 hours. The scrape usually completes well
    within that window, but if the remote site stalls or Playwright hangs, a
    second cron tick should not launch a concurrent browser session against the
    same clinic account or tracker/database outputs.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logging.getLogger(__name__).info(
            "Another kathia_schedule run is already active "
            "(lock held on %s) — exiting quietly.",
            LOCK_PATH,
        )
        sys.exit(0)
    globals()["_SINGLETON_LOCK_FD"] = lock_fd


def _record_pull(status: str, data: dict | None = None, error: str | None = None) -> None:
    """Persist the timestamp and summary of the most recent clinic pull.

    Written atomically so a concurrent read never sees a half-written file.
    """
    now = datetime.now(timezone.utc)
    entry = {
        "last_attempt_at": now.isoformat(),
        "last_attempt_status": status,
    }
    if status == "ok":
        entry["last_success_at"] = now.isoformat()
        entry["rows_saved"] = (data or {}).get("rows_saved", 0)
        entry["ai_triggered"] = (data or {}).get("ai_triggered", 0)
        entry["days"] = (data or {}).get("days", [])
    if error:
        entry["error"] = error

    # Preserve last_success_at across failed attempts.
    if status != "ok" and TRACKER_PATH.exists():
        try:
            prior = json.loads(TRACKER_PATH.read_text())
            if prior.get("last_success_at"):
                entry["last_success_at"] = prior["last_success_at"]
                entry["rows_saved"] = prior.get("rows_saved")
                entry["ai_triggered"] = prior.get("ai_triggered")
                entry["days"] = prior.get("days")
        except Exception:
            pass

    tmp = TRACKER_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entry, indent=2))
    tmp.replace(TRACKER_PATH)


async def main() -> None:
    seq = KathiaScheduleSequence()
    try:
        result = await seq.run()
    except Exception as e:
        _record_pull("error", error=str(e))
        raise
    if result.get("ok"):
        data = result.get("data", {})
        _record_pull("ok", data=data)
        print(f"OK — {data.get('rows_saved', 0)} appointments saved, "
              f"AI triggered: {data.get('ai_triggered', 0)}, "
              f"days: {data.get('days', [])}")
    else:
        err = result.get("error", "unknown error")
        _record_pull("error", error=err)
        print(f"FAILED — {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _acquire_singleton_lock()
    asyncio.run(main())
