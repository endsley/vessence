#!/usr/bin/env python3
"""Post the latest audit result into Jane web announcements around 11:00 AM."""

import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import LOGS_DIR, VESSENCE_DATA_HOME

LOG_FILE = Path(LOGS_DIR) / "audit_result_notify.log"
AUDIT_LOG_DIR = Path(LOGS_DIR) / "audits"
LATEST_AUDIT_SUMMARY = AUDIT_LOG_DIR / "latest_audit_summary.json"
ANNOUNCEMENTS_PATH = Path(VESSENCE_DATA_HOME) / "data" / "jane_announcements.jsonl"
STATE_PATH = Path(VESSENCE_DATA_HOME) / "data" / "audit_web_notification_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [notify_audit_results] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)],
)
logger = logging.getLogger("notify_audit_results")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    tmp_path.replace(path)


def _load_latest_audit() -> dict:
    payload = _load_json(LATEST_AUDIT_SUMMARY)
    if payload.get("report"):
        return payload

    reports = sorted(AUDIT_LOG_DIR.glob("audit_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return {}
    report_path = reports[0]
    report = report_path.read_text().strip()
    generated_at = datetime.datetime.fromtimestamp(report_path.stat().st_mtime, tz=datetime.timezone.utc).isoformat()
    return {
        "generated_at": generated_at,
        "report_path": str(report_path),
        "report": report,
    }


def _extract_brief(report: str) -> str:
    text = re.sub(r"^#.*$", "", report, flags=re.MULTILINE).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= 2200:
        return text
    return text[:2197].rstrip() + "..."


def _write_announcement(message: str, announcement_id: str) -> None:
    ANNOUNCEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "queue_progress",
        "id": announcement_id,
        "message": message,
        "final": True,
    }
    with ANNOUNCEMENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    today = datetime.date.today().isoformat()
    state = _load_json(STATE_PATH)
    if state.get("last_notified_date") == today:
        logger.info("Already notified for %s", today)
        return

    latest = _load_latest_audit()
    report = latest.get("report", "").strip()
    generated_at = latest.get("generated_at", "")
    if not report or not generated_at:
        logger.info("No audit report available to notify.")
        return

    try:
        generated_dt = datetime.datetime.fromisoformat(generated_at)
    except ValueError:
        logger.warning("Invalid generated_at in audit summary: %s", generated_at)
        return

    age = datetime.datetime.now(generated_dt.tzinfo or datetime.timezone.utc) - generated_dt
    if age > datetime.timedelta(hours=36):
        logger.info("Latest audit is too old to notify (%s)", generated_at)
        return

    local_stamp = generated_dt.astimezone().strftime("%Y-%m-%d %I:%M %p")
    brief = _extract_brief(report)
    message = (
        f"**Morning audit summary**\n"
        f"Latest audit run: {local_stamp}\n\n"
        f"{brief}"
    )
    announcement_id = f"audit_result_{today}"
    _write_announcement(message, announcement_id)
    _save_json(STATE_PATH, {
        "last_notified_date": today,
        "last_report_generated_at": generated_at,
        "announcement_id": announcement_id,
    })
    logger.info("Posted audit announcement for %s", today)


if __name__ == "__main__":
    main()
