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

from agent_skills.self_healing_storage import (
    PrivateJsonLockUnavailable,
    atomic_write_private_json,
)

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
    incident_requests_critical_auto_repair as _incident_requests_critical_auto_repair,
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
DEFERRED_CAPTURE_DIR = SELF_HEAL_DIR / "deferred_captures"

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
    try:
        return _record_incident(incident, auto_repair=auto_repair)
    except Exception as capture_exc:
        logger.warning("self-healing exception capture deferred: %s", type(capture_exc).__name__)
        return _defer_incident_capture(incident, auto_repair=auto_repair)


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
    try:
        return _record_incident(incident, auto_repair=auto_repair)
    except Exception as capture_exc:
        logger.warning("self-healing report capture deferred: %s", type(capture_exc).__name__)
        return _defer_incident_capture(incident, auto_repair=auto_repair)


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
        # A failure that returns after a repair reached a terminal outcome is
        # a new repair event, not merely a duplicate log line.  Keeping it
        # deduped would leave the watchdog looking only at the prior finished
        # incident and suppress Codex/Claude handoff for up to the sliding
        # rate-limit window.
        if dedupe["deduped"] and _dedupe_record_has_terminal_incident(record):
            dedupe = {"deduped": False, "count": dedupe["count"]}
        # A critical Waterlily repair deliberately retries until a verified
        # nightly report succeeds.  It is therefore one continuing recovery
        # event, not a new Codex/Claude worker every time the same UI failure
        # recurs after the ordinary log-rate window.  Otherwise a persistent
        # vendor outage can create overlapping incident files and eventually
        # strand a live report behind an unrelated repair-project lease.
        if not dedupe["deduped"] and _dedupe_record_has_active_critical_incident(record):
            count = int(dedupe["count"])
            continued_record = dict(record)
            continued_record.update({
                "last_seen_at": incident["created_at"],
                "last_seen_ts": now_ts,
                "count": count,
            })
            dedupe = {
                "deduped": True,
                "count": count,
                "record": continued_record,
                "incident_updates": {
                    "deduped": True,
                    "occurrence_count": count,
                    "incident_path": record.get("incident_path"),
                    "job_path": record.get("job_path"),
                },
            }
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
            atomic_write_private_json(incident_path, incident)
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


def _dedupe_record_has_terminal_incident(record: dict[str, Any]) -> bool:
    """Return true only for a safely-local terminal incident record."""
    raw_path = str(record.get("incident_path") or "").strip()
    if not raw_path:
        return False
    try:
        incident_path = Path(raw_path).expanduser().resolve()
        incident_root = INCIDENT_DIR.resolve()
    except Exception:
        return False
    if incident_path.parent != incident_root:
        return False
    try:
        payload = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("status") or "").strip() in {
        "repair_finished",
        "repair_failed",
        "repaired",
    }


def _dedupe_record_has_active_critical_incident(record: dict[str, Any]) -> bool:
    """Return true only for an unresolved critical incident at its safe path.

    This intentionally does not dedupe ordinary errors indefinitely: only the
    no-timeout critical recovery loop has a durable guarantee that the same
    incident will be retried until report verification.  Path containment and
    JSON validation prevent a state record from suppressing unrelated work.
    """
    raw_path = str(record.get("incident_path") or "").strip()
    if not raw_path:
        return False
    try:
        incident_path = Path(raw_path).expanduser().resolve()
        incident_root = INCIDENT_DIR.resolve()
    except Exception:
        return False
    if incident_path.parent != incident_root:
        return False
    try:
        payload = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict) or not _incident_requests_critical_auto_repair(payload):
        return False
    return str(payload.get("status") or "").strip() in {
        "captured",
        "repair_started",
        "repair_attempting",
        "repair_retrying",
    }


def _deferred_capture_path(incident: dict[str, Any]) -> Path:
    """Return a private unique spool path without using source error text."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    incident_id = _slugify(str(incident.get("id") or "incident"), 48)
    return DEFERRED_CAPTURE_DIR / f"{stamp}-{os.getpid()}-{incident_id}.json"


def _defer_incident_capture(
    incident: dict[str, Any],
    *,
    auto_repair: bool | None,
) -> dict[str, Any] | None:
    """Durably preserve a failed capture for the five-minute watchdog.

    This is intentionally disabled inside an active repair worker to avoid a
    broken capture backend recursively creating repair incidents about itself.
    The payload is the already-built private incident object that would have
    been written normally; no new request/source text is added here.
    """
    if os.environ.get("JANE_SELF_HEAL_ACTIVE") == "1":
        return None
    try:
        path = _deferred_capture_path(incident)
        atomic_write_private_json(
            path,
            {
                "version": 1,
                "incident": _jsonable(incident),
                "auto_repair": auto_repair if isinstance(auto_repair, bool) else None,
                "deferred_at": _now_iso(),
            },
        )
    except Exception as spool_exc:
        logger.warning("self-healing deferred-capture spool failed: %s", type(spool_exc).__name__)
        return None
    return {
        "id": str(incident.get("id") or ""),
        "status": "deferred",
        "deduped": False,
        "occurrence_count": 0,
    }


def drain_deferred_captures() -> int:
    """Replay private capture spools; keep failures for the next watchdog."""
    if os.environ.get("JANE_SELF_HEAL_ACTIVE") == "1" or not DEFERRED_CAPTURE_DIR.is_dir():
        return 0
    drained = 0
    for path in sorted(DEFERRED_CAPTURE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            incident = payload.get("incident") if isinstance(payload, dict) else None
            auto_repair = payload.get("auto_repair") if isinstance(payload, dict) else None
            if not isinstance(incident, dict) or not isinstance(auto_repair, (bool, type(None))):
                continue
            _record_incident(incident, auto_repair=auto_repair)
        except Exception as exc:
            logger.warning("self-healing deferred capture remains queued: %s", type(exc).__name__)
            continue
        try:
            path.unlink()
        except OSError:
            continue
        drained += 1
    return drained


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
    try:
        incident = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        incident = {}
    critical = _incident_requests_critical_auto_repair(incident)
    if not critical:
        try:
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
        except PrivateJsonLockUnavailable:
            # The incident is already durable.  Do not make an incoming
            # request wait behind a stale state lock or spool it a second
            # time; the watchdog/job queue can launch it after the lease is
            # available.
            logger.warning("self-healing auto repair launch deferred: state lock unavailable")
            return
    else:
        logger.warning("self-healing critical auto repair bypassing cooldown for %s", incident_path)

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
            # Keep the durable repair worker independent of the failed request
            # or scheduled child that launched it.  Its own per-incident lock
            # prevents duplicate watchdog/manual launches.
            subprocess.Popen(
                cmd,
                cwd=str(VESSENCE_HOME),
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
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
    try:
        SELF_HEAL_DIR.chmod(0o700)
    except OSError:
        pass
    lock_path = SELF_HEAL_DIR / "state.lock"
    with lock_path.open("a+") as lock_fh:
        try:
            lock_path.chmod(0o600)
        except OSError:
            pass
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PrivateJsonLockUnavailable("self-healing state lock unavailable") from exc
        try:
            state = _read_state()
            yield state
        finally:
            try:
                atomic_write_private_json(STATE_PATH, state)
            finally:
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
