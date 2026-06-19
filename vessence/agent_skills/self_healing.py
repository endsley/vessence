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
import hashlib
import json
import logging
import os
import re
import subprocess
import traceback
from pathlib import Path
from typing import Any

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

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "x-csrf-token",
    "x-jane-self-heal-token",
    "x-api-key",
}


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
        headers = {}
        for key, value in getattr(request, "headers", {}).items():
            lk = key.lower()
            if lk in SENSITIVE_HEADER_NAMES:
                headers[key] = "[redacted]"
            elif lk.startswith("x-") or lk in {"host", "referer", "user-agent", "content-type"}:
                headers[key] = str(value)[:500]
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
        last_seen = float(record.get("last_seen_ts") or 0)
        count = int(record.get("count") or 0) + 1
        if last_seen and now_ts - last_seen < DEFAULT_RATE_LIMIT_SEC:
            deduped = True
            record.update({
                "last_seen_at": incident["created_at"],
                "last_seen_ts": now_ts,
                "count": count,
            })
            fingerprints[incident["fingerprint"]] = record
            incident.update({
                "deduped": True,
                "occurrence_count": count,
                "incident_path": record.get("incident_path"),
                "job_path": record.get("job_path"),
            })
        else:
            incident["occurrence_count"] = count
            incident_path = INCIDENT_DIR / f"{incident['created_at'].replace(':', '').replace('-', '')}_{incident['id']}.json"
            job_path = _create_job_for_incident(incident, incident_path)
            incident.update({
                "deduped": False,
                "incident_path": str(incident_path),
                "job_path": str(job_path),
            })
            incident_path.write_text(json.dumps(incident, indent=2, sort_keys=True), encoding="utf-8")
            record = {
                "first_seen_at": record.get("first_seen_at") or incident["created_at"],
                "last_seen_at": incident["created_at"],
                "last_seen_ts": now_ts,
                "count": count,
                "incident_path": str(incident_path),
                "job_path": str(job_path),
                "source": incident["source"],
                "category": incident["category"],
            }
            fingerprints[incident["fingerprint"]] = record

    _append_jsonl(incident)
    if not deduped and _should_auto_repair(auto_repair):
        _maybe_launch_auto_repair(Path(incident["incident_path"]))
    return incident


def _create_job_for_incident(incident: dict[str, Any], incident_path: Path) -> Path:
    num = _next_job_number()
    source = _slugify(str(incident.get("source", "unknown")), 28)
    category = _slugify(str(incident.get("category", "incident")), 24)
    job_path = JOB_QUEUE_DIR / f"job_{num:03d}_self_heal_{source}_{category}.md"
    title = f"Self-heal {incident.get('source', 'unknown')}: {incident_title(incident)}"
    project_root = incident.get("project_root") or str(VESSENCE_HOME)
    body = f"""# Job: {title}
Status: pending
Priority: high
Created: {dt.date.today().isoformat()}
Auto-generated: true
Source: jane_self_healing
Incident: {incident_path}

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `{incident.get("source", "")}`
- Category: `{incident.get("category", "")}`
- Project root: `{project_root}`
- Fingerprint: `{incident.get("fingerprint", "")}`
- Request path: `{incident.get("request", {}).get("path", "")}`

## Steps
1. Read the incident JSON at `{incident_path}` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.
"""
    job_path.write_text(body, encoding="utf-8")
    return job_path


def incident_title(incident: dict[str, Any]) -> str:
    if incident.get("category") == "exception":
        exc = incident.get("exception", {})
        return f"{exc.get('type', 'Exception')} at {incident.get('request', {}).get('path', '') or exc.get('top_frame', '')}"
    payload = incident.get("payload", {})
    return str(payload.get("exception_class") or incident.get("message") or incident.get("category"))[:120]


def _maybe_launch_auto_repair(incident_path: Path) -> None:
    if not incident_path.exists():
        return
    with _locked_state() as state:
        now = dt.datetime.now(dt.timezone.utc)
        today = now.date().isoformat()
        day = state.setdefault("auto_repair_day", today)
        if day != today:
            state["auto_repair_day"] = today
            state["auto_repair_count"] = 0
        count = int(state.get("auto_repair_count") or 0)
        if count >= DEFAULT_MAX_AUTO_REPAIRS_PER_DAY:
            logger.warning("self-healing auto repair daily cap reached (%s)", count)
            return
        last = float(state.get("last_auto_repair_ts") or 0)
        now_ts = now.timestamp()
        if last and now_ts - last < DEFAULT_REPAIR_COOLDOWN_SEC:
            logger.info("self-healing auto repair cooldown active")
            return
        state["last_auto_repair_ts"] = now_ts
        state["last_auto_repair_at"] = now.isoformat()
        state["auto_repair_count"] = count + 1

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
    if auto_repair is not None:
        return auto_repair
    return os.environ.get("JANE_SELF_HEAL_AUTO_REPAIR", "1").strip().lower() not in {"0", "false", "no", "off"}


def _enabled() -> bool:
    return os.environ.get("JANE_SELF_HEALING", "1").strip().lower() not in {"0", "false", "no", "off"}


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


def _first_stack_frame(stack: str) -> str:
    for line in stack.splitlines():
        clean = line.strip()
        if clean.startswith("at ") or clean.startswith("File "):
            return clean[:240]
    return ""


def _fingerprint(*parts: str) -> str:
    joined = "\n".join(str(part or "") for part in parts)
    return hashlib.sha256(joined.encode("utf-8", errors="replace")).hexdigest()[:24]


def _incident_id(source: str, fingerprint: str) -> str:
    return f"{_slugify(source, 32)}_{fingerprint}"


def _slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return (slug[:max_len] or "incident").strip("_") or "incident"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))


if __name__ == "__main__":
    try:
        raise RuntimeError("self-healing smoke test")
    except RuntimeError as exc:
        result = capture_exception(source="self_healing_smoke", exc=exc, auto_repair=False)
        print(json.dumps(result, indent=2))
