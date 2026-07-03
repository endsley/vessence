"""Self-healing incident capture for Jane/Vessence projects.

This module is intentionally small at request time: capture the failure,
create durable evidence, open a repair job, and optionally launch the
autonomous repair runner in the background. The repair runner is where LLM
inspection and code changes happen.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import logging
import os
import re
import subprocess
import traceback
from pathlib import Path
from typing import Any

from agent_skills.self_healing_helpers import (
    SENSITIVE_HEADER_NAMES,
    auto_repair_launch_decision as _auto_repair_launch_decision,
    build_self_heal_job_markdown as _build_self_heal_job_markdown,
    env_flag_enabled as _env_flag_enabled,
    fingerprint as _fingerprint,
    first_stack_frame as _first_stack_frame,
    incident_id as _incident_id,
    incident_json_path as _incident_json_path,
    incident_title_text as _incident_title_text,
    jsonable as _jsonable,
    incident_dedupe_result as _incident_dedupe_result,
    new_incident_fingerprint_record as _new_incident_fingerprint_record,
    redacted_request_headers as _redacted_request_headers,
    self_heal_job_path as _self_heal_job_path,
    should_auto_repair as _should_auto_repair_with_env,
    slugify as _slugify,
)

logger = logging.getLogger(__name__)

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
PYTHON = os.environ.get("VESSENCE_PYTHON", "/home/chieh/google-adk-env/adk-venv/bin/python")

SELF_HEAL_DIR = VESSENCE_DATA_HOME / "self_healing"
INCIDENT_DIR = SELF_HEAL_DIR / "incidents"
STATE_PATH = SELF_HEAL_DIR / "state.json"
LOG_DIR = VESSENCE_DATA_HOME / "logs"
JSONL_LOG = LOG_DIR / "self_healing.jsonl"
JOB_QUEUE_DIR = VESSENCE_HOME / "configs" / "job_queue"

DEFAULT_RATE_LIMIT_SEC = int(os.environ.get("JANE_SELF_HEAL_RATE_LIMIT_SEC", "900"))
DEFAULT_REPAIR_COOLDOWN_SEC = int(os.environ.get("JANE_SELF_HEAL_REPAIR_COOLDOWN_SEC", "1800"))
DEFAULT_MAX_AUTO_REPAIRS_PER_DAY = int(os.environ.get("JANE_SELF_HEAL_MAX_AUTO_REPAIRS_PER_DAY", "3"))

def capture_exception(
    *,
    source: str,
    exc: BaseException,
    request: Any | None = None,
    request_info: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
    context: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    auto_repair: bool | None = None,
) -> dict[str, Any] | None:
    """Capture an exception and schedule self-healing.

    Returns the incident summary dict, or None if self-healing is disabled.
    """
    if not _enabled():
        return None
    if os.environ.get("JANE_SELF_HEAL_ACTIVE") == "1":
        return None

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    top_frame = _top_frame(exc)
    req = request_info or request_info_from_request(request)
    exc_type = type(exc).__name__
    message = str(exc)
    fingerprint = _fingerprint(
        source,
        "exception",
        exc_type,
        top_frame or "",
        req.get("path", ""),
    )
    incident = {
        "id": _incident_id(source, fingerprint),
        "status": "captured",
        "source": source,
        "category": "exception",
        "created_at": _now_iso(),
        "fingerprint": fingerprint,
        "project_root": str(project_root or VESSENCE_HOME),
        "request": req,
        "exception": {
            "type": exc_type,
            "message": message,
            "top_frame": top_frame,
            "traceback": tb[-20000:],
        },
        "context": _jsonable(context or {}),
        "tags": tags or [],
    }
    return _record_incident(incident, auto_repair=auto_repair)


def capture_report(
    *,
    source: str,
    category: str,
    message: str = "",
    payload: dict[str, Any] | None = None,
    request: Any | None = None,
    request_info: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
    tags: list[str] | None = None,
    auto_repair: bool | None = None,
) -> dict[str, Any] | None:
    """Capture a non-Python diagnostic report, such as Android or remote app errors."""
    if not _enabled():
        return None
    if os.environ.get("JANE_SELF_HEAL_ACTIVE") == "1":
        return None

    payload = _jsonable(payload or {})
    req = request_info or request_info_from_request(request)
    fingerprint_seed = (
        payload.get("exception_class")
        or payload.get("first_app_frame")
        or _first_stack_frame(str(payload.get("stack_trace", "")))
        or message[:180]
    )
    reported_request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    reported_path = str(reported_request.get("path") or "")
    fingerprint = _fingerprint(
        source,
        category,
        str(fingerprint_seed),
        req.get("path", ""),
        reported_path,
    )
    incident = {
        "id": _incident_id(source, fingerprint),
        "status": "captured",
        "source": source,
        "category": category,
        "created_at": _now_iso(),
        "fingerprint": fingerprint,
        "project_root": str(project_root or VESSENCE_HOME),
        "request": req,
        "message": message,
        "payload": payload,
        "tags": tags or [],
    }
    return _record_incident(incident, auto_repair=auto_repair)


def request_info_from_request(request: Any | None) -> dict[str, Any]:
    """Extract non-secret request details from a FastAPI/Starlette request."""
    if request is None:
        return {}
    try:
        headers = _redacted_request_headers(getattr(request, "headers", {}))
        url = getattr(request, "url", None)
        client = getattr(request, "client", None)
        return {
            "method": getattr(request, "method", ""),
            "path": getattr(url, "path", "") if url is not None else "",
            "query": str(getattr(url, "query", ""))[:1000] if url is not None else "",
            "client": getattr(client, "host", "") if client is not None else "",
            "headers": headers,
        }
    except Exception:
        return {}


def _record_incident(incident: dict[str, Any], *, auto_repair: bool | None) -> dict[str, Any] | None:
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    JOB_QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    deduped = False
    with _locked_state() as state:
        fingerprints = state.setdefault("fingerprints", {})
        record = fingerprints.get(incident["fingerprint"], {})
        now_ts = dt.datetime.now(dt.timezone.utc).timestamp()
        dedupe = _incident_dedupe_result(
            record,
            incident,
            now_ts=now_ts,
            rate_limit_sec=DEFAULT_RATE_LIMIT_SEC,
        )
        if dedupe["deduped"]:
            deduped = True
            fingerprints[incident["fingerprint"]] = dedupe["record"]
            incident.update(dedupe["incident_updates"])
        else:
            incident["occurrence_count"] = dedupe["count"]
            incident_path = _incident_json_path(INCIDENT_DIR, incident)
            job_path = _create_job_for_incident(incident, incident_path)
            incident.update({
                "deduped": False,
                "incident_path": str(incident_path),
                "job_path": str(job_path),
            })
            incident_path.write_text(json.dumps(incident, indent=2, sort_keys=True), encoding="utf-8")
            fingerprints[incident["fingerprint"]] = _new_incident_fingerprint_record(
                record,
                incident,
                now_ts=now_ts,
                incident_path=incident_path,
                job_path=job_path,
            )

    _append_jsonl(incident)
    if not deduped and _should_auto_repair(auto_repair):
        _maybe_launch_auto_repair(Path(incident["incident_path"]))
    return incident


def _create_job_for_incident(incident: dict[str, Any], incident_path: Path) -> Path:
    num = _next_job_number()
    job_path = _self_heal_job_path(JOB_QUEUE_DIR, num, incident)
    body = _build_self_heal_job_markdown(
        incident,
        incident_path,
        created_date=dt.date.today(),
        default_project_root=VESSENCE_HOME,
    )
    job_path.write_text(body, encoding="utf-8")
    return job_path


def incident_title(incident: dict[str, Any]) -> str:
    return _incident_title_text(incident)


def _maybe_launch_auto_repair(incident_path: Path) -> None:
    if not incident_path.exists():
        return
    with _locked_state() as state:
        now = dt.datetime.now(dt.timezone.utc)
        decision = _auto_repair_launch_decision(
            state,
            now=now,
            max_per_day=DEFAULT_MAX_AUTO_REPAIRS_PER_DAY,
            cooldown_sec=DEFAULT_REPAIR_COOLDOWN_SEC,
        )
        if decision == "daily_cap":
            logger.warning(
                "self-healing auto repair daily cap reached (%s)",
                int(state.get("auto_repair_count") or 0),
            )
            return
        if decision == "cooldown":
            logger.info("self-healing auto repair cooldown active")
            return

    log_path = LOG_DIR / "self_healing_repair.log"
    env = {
        **os.environ,
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
        "JANE_SELF_HEAL_ACTIVE": "1",
    }
    cmd = [PYTHON, str(VESSENCE_HOME / "agent_skills" / "self_healing_repair.py"), "--incident", str(incident_path)]
    try:
        with log_path.open("a", encoding="utf-8") as logf:
            logf.write(f"\n===== self-healing launch {dt.datetime.now().isoformat()} incident={incident_path} =====\n")
            subprocess.Popen(cmd, cwd=str(VESSENCE_HOME), env=env, stdout=logf, stderr=subprocess.STDOUT)
        logger.info("self-healing auto repair launched for %s", incident_path)
    except Exception as exc:
        logger.warning("self-healing auto repair launch failed: %s", exc)


def _should_auto_repair(auto_repair: bool | None) -> bool:
    return _should_auto_repair_with_env(auto_repair, os.environ)


def _enabled() -> bool:
    return _env_flag_enabled(os.environ, "JANE_SELF_HEALING", "1")


@contextlib.contextmanager
def _locked_state():
    SELF_HEAL_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = SELF_HEAL_DIR / "state.lock"
    with lock_path.open("a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        state = _read_state()
        try:
            yield state
        finally:
            STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def _read_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _append_jsonl(payload: dict[str, Any]) -> None:
    try:
        with JSONL_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("self-healing JSONL write failed: %s", exc)


def _next_job_number() -> int:
    highest = 0
    for base in (JOB_QUEUE_DIR, JOB_QUEUE_DIR / "completed"):
        if not base.exists():
            continue
        for path in base.glob("*.md"):
            match = re.match(r"^(?:job_)?(\d+)", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def _top_frame(exc: BaseException) -> str:
    tb = exc.__traceback__
    last = None
    while tb is not None:
        last = tb
        tb = tb.tb_next
    if last is None:
        return ""
    frame = last.tb_frame
    return f"{frame.f_code.co_filename}:{last.tb_lineno}:{frame.f_code.co_name}"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


if __name__ == "__main__":
    try:
        raise RuntimeError("self-healing smoke test")
    except RuntimeError as exc:
        result = capture_exception(source="self_healing_smoke", exc=exc, auto_repair=False)
        print(json.dumps(result, indent=2))
