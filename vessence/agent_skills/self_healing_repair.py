#!/usr/bin/env python3
"""Autonomous repair runner for captured self-healing incidents.

Critical Waterlily nightly incidents are not considered repaired merely because
an LLM returned prose.  They remain active until the repaired code produces a
fresh, successful nightly report summary.  Individual providers may time out,
but the critical repair workflow retries with backoff rather than terminally
failing on that timeout.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from agent_skills.self_healing_storage import compare_and_update_private_json, update_private_json
from agent_skills.self_healing_helpers import env_flag_enabled

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
PYTHON = os.environ.get("VESSENCE_PYTHON", "/home/chieh/google-adk-env/adk-venv/bin/python")
LOG_DIR = VESSENCE_DATA_HOME / "logs"
SELF_HEAL_DIR = VESSENCE_DATA_HOME / "self_healing"
INCIDENT_DIR = SELF_HEAL_DIR / "incidents"
REPORT_DIR = SELF_HEAL_DIR / "reports"
WATERLILY_DEFAULT_ROOT = Path("/home/chieh/code/waterlily")
WATERLILY_NIGHTLY_SOURCE = "waterlily_nightly_reports"
WATERLILY_NIGHTLY_RUNNER = Path("scripts/run_nightly_current_month_reports.py")
WATERLILY_NIGHTLY_SUMMARY = Path("logs/waterlily_nightly_reports/latest.json")
WATERLILY_NIGHTLY_LOCK = Path("/tmp/waterlily-nightly-current-month-reports.lock")
WATERLILY_NIGHTLY_PROGRESS_RELATIVE = Path("logs/waterlily_nightly_reports/progress")
WATERLILY_NIGHTLY_TZ = ZoneInfo("America/New_York")
WATERLILY_NIGHTLY_SCHEDULE_HOUR = 1
WATERLILY_NIGHTLY_SCHEDULE_MINUTE = 30
REPAIR_PROVIDER_FAILURE_MESSAGE = (
    "**Waterlily self-healing needs attention**\n"
    "Codex and Claude could not complete this repair. Automatic retries continue."
)
GENERIC_REPAIR_PROVIDER_FAILURE_MESSAGE = (
    "**Self-healing repair needs attention**\n"
    "Codex and Claude could not complete this repair."
)
_CRITICAL_REPAIR_PROVIDERS = frozenset({"codex", "claude"})
# A detached repair worker handles one incident at a time.  This in-process
# pointer lets the no-timeout regeneration poll publish only safe liveness
# metadata for that worker; it never stores a command, prompt, or output.
_ACTIVE_REPAIR_INCIDENT_PATH: Path | None = None
_UNCHANGED = object()


@dataclass(frozen=True)
class RepairCompletion:
    """Private LLM output plus safe provider metadata for one repair attempt."""

    output: str
    provider: str
    failed_providers: tuple[str, ...] = ()

sys.path.insert(0, str(VESSENCE_HOME))


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _waterlily_project_root() -> Path:
    """Return the one allowlisted project whose repair verifies regeneration."""
    configured = os.environ.get("JANE_WATERLILY_PROJECT_ROOT", str(WATERLILY_DEFAULT_ROOT))
    return Path(configured).expanduser().resolve()


@contextlib.contextmanager
def _incident_repair_lock(incident_path: Path):
    """Prevent duplicate work on one incident without blocking other repairs."""
    SELF_HEAL_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(incident_path).encode("utf-8")).hexdigest()[:20]
    path = SELF_HEAL_DIR / f"repair-{digest}.lock"
    with path.open("a+") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _incident_repair_lock_is_held(incident_path: Path) -> bool:
    """Check one durable incident lease without guessing about its owner.

    Older repair workers predate the persisted ``repair_worker`` PID/start-
    tick lease.  Their incident flock is still authoritative evidence that a
    worker may be active, so the watchdog must not launch a replacement just
    because the JSON has no current worker record.  A filesystem error is
    conservatively treated as held; it is never permission to duplicate an
    unattended repair.
    """
    try:
        with _incident_repair_lock(incident_path) as acquired:
            return not acquired
    except OSError:
        return True


@contextlib.contextmanager
def _waterlily_project_repair_lease():
    """Serialize provider edits/regeneration across all Waterlily incidents.

    This is deliberately nonblocking: a second incident remains durable and
    the five-minute watchdog retries it after the first project repair exits.
    It prevents two Codex/Claude sessions from editing or regenerating the
    same Waterlily repository concurrently.
    """
    SELF_HEAL_DIR.mkdir(parents=True, exist_ok=True)
    path = SELF_HEAL_DIR / "waterlily-project-repair.lock"
    with path.open("a+") as fh:
        try:
            path.chmod(0o600)
        except OSError:
            pass
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _allowed_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    configured = os.environ.get("JANE_SELF_HEAL_PROJECT_ROOTS", "")
    allowed = [
        VESSENCE_HOME.resolve(),
        Path("/home/chieh/code/chieh_class_v2").resolve(),
        _waterlily_project_root(),
    ]
    for item in configured.split(":"):
        if item.strip():
            allowed.append(Path(item).expanduser().resolve())
    if any(root == base or base in root.parents for base in allowed):
        return root
    raise SystemExit(f"Refusing self-healing outside allowed project roots: {root}")


def _read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-limit:] if len(text) > limit else text


def _collect_log_context(source: str, project_root: Path) -> str:
    """Collect generic project logs only; Waterlily incidents are sanitized."""
    if project_root == _waterlily_project_root() or source == WATERLILY_NIGHTLY_SOURCE:
        return ""
    chunks: list[str] = []
    candidates = [
        LOG_DIR / "jane_web.log",
        LOG_DIR / "self_healing.jsonl",
        LOG_DIR / "job_queue_runner.log",
        project_root / "PanGPA.log",
    ]
    for path in candidates:
        text = _read_text(path)
        if text:
            chunks.append(f"===== {path} (tail) =====\n{text}")
    return "\n\n".join(chunks)[-24000:]


def _write_private_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _append_private_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _write_incident_update(path: Path, **updates: Any) -> bool:
    try:
        update_private_json(path, updates)
        return True
    except Exception:
        # An incident update must not interrupt a repair that is still able to
        # fix the underlying report problem.
        return False


def _process_start_ticks_and_state(pid: int) -> tuple[str, str] | None:
    """Return Linux process start ticks + state without reading its command.

    PID alone is unsafe after a crash because the OS may reuse it.  The start
    tick from ``/proc/<pid>/stat`` proves that a persisted worker lease still
    refers to the same process while keeping process arguments (which could
    contain a repair prompt) out of durable incident state.
    """
    if int(pid or 0) <= 0:
        return None
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        closing = raw.rfind(")")
        fields = raw[closing + 2 :].split() if closing >= 0 else []
        # After ``pid (comm)``, index 0 is process state (field 3) and index
        # 19 is starttime (field 22).  Do not parse ``comm`` itself.
        state = str(fields[0] or "")
        start_ticks = str(fields[19] or "")
    except (OSError, IndexError, ValueError):
        return None
    if not state or not start_ticks.isdigit():
        return None
    return start_ticks, state


def _process_lease_liveness(lease: Any) -> str:
    """Classify a safe PID/start-tick lease without killing a live process."""
    if not isinstance(lease, dict):
        return "none"
    try:
        pid = int(lease.get("pid") or 0)
    except (TypeError, ValueError):
        return "none"
    observed = _process_start_ticks_and_state(pid)
    if observed is None:
        return "lost"
    start_ticks, state = observed
    expected_ticks = str(lease.get("start_ticks") or "")
    if expected_ticks and start_ticks != expected_ticks:
        return "reused"
    if state.upper() == "Z":
        # A zombie no longer executes or owns a useful repair lock, even if
        # init has not reaped its PID yet.
        return "lost"
    if state.upper() == "T":
        return "stopped"
    # If an old incident lacks a start-tick, do not risk a duplicate worker;
    # it will be reclaimed only after the PID disappears.
    return "live" if expected_ticks else "live_unverified"


def _repair_worker_liveness(incident: dict[str, Any]) -> str:
    """Classify a persisted repair-worker lease without killing it."""
    worker = incident.get("repair_worker")
    return _process_lease_liveness(worker)


def _repair_regeneration_child_liveness(incident: dict[str, Any]) -> str:
    """Classify a persisted no-timeout nightly child lease, if one exists."""
    worker = incident.get("repair_worker")
    child = worker.get("regeneration_child") if isinstance(worker, dict) else None
    return _process_lease_liveness(child)


def _safe_provider_child_lease(value: Any) -> dict[str, Any] | None:
    """Validate the exact, privacy-safe lease for one repair provider child.

    Providers are separate process groups because a timed-out Codex must not
    survive into Claude's fallback.  The repair watchdog needs the same exact
    PID/start-tick proof before it can decide whether a crashed parent may be
    replaced.  Keep the record deliberately finite: provider enum plus Linux
    process identity, never a CLI command, prompt, response, or model name.
    """
    if not isinstance(value, dict) or set(value) != {"provider", "pid", "start_ticks"}:
        return None
    provider = str(value.get("provider") or "").strip().lower()
    if provider not in _CRITICAL_REPAIR_PROVIDERS:
        return None
    lease = _safe_regeneration_child_lease(value)
    if lease is None:
        return None
    return {"provider": provider, **lease}


def _repair_provider_child_liveness(incident: dict[str, Any]) -> str:
    """Classify a persisted provider child before replacing a repair parent."""
    worker = incident.get("repair_worker")
    child = worker.get("provider_child") if isinstance(worker, dict) else None
    return _process_lease_liveness(_safe_provider_child_lease(child))


def _safe_regeneration_child_lease(value: Any) -> dict[str, Any] | None:
    """Return only a valid child PID/start-tick pair from durable state."""
    if not isinstance(value, dict):
        return None
    try:
        pid = int(value.get("pid") or 0)
    except (TypeError, ValueError):
        return None
    start_ticks = str(value.get("start_ticks") or "")
    if pid <= 0 or not start_ticks.isdigit():
        return None
    return {"pid": pid, "start_ticks": start_ticks}


def _safe_regeneration_orphan(value: Any) -> dict[str, Any] | None:
    """Validate the one safe handoff left by a crashed scheduler wrapper.

    A repair worker launches the lock-owning scheduler wrapper, and that
    wrapper launches the actual updater in its own session.  If only the
    wrapper dies, the updater may legitimately continue.  Keep the durable
    handoff deliberately small: exact process leases plus a protocol version.
    In particular, it must never contain a source URL, DOM text, command line,
    report row, or provider output.
    """
    if not isinstance(value, dict) or set(value) != {"version", "wrapper", "updater"}:
        return None
    if value.get("version") != 1:
        return None
    wrapper = _safe_regeneration_child_lease(value.get("wrapper"))
    updater = _safe_regeneration_child_lease(value.get("updater"))
    if wrapper is None or updater is None:
        return None
    return {"version": 1, "wrapper": wrapper, "updater": updater}


def _active_regeneration_orphan_candidate(wrapper_lease: Any) -> dict[str, Any] | None:
    """Prove that one dead wrapper still has its exact live updater.

    The Waterlily progress protocol owns the active pointer and rejects an
    unsafe/stale schema before this function sees it.  We accept a candidate
    only when that pointer is still owned by the exact durable wrapper lease
    and its updater has the matching Linux start ticks.  This is evidence to
    *avoid* parallel repair work; a missing or malformed pointer is never
    evidence to signal a process or manufacture an orphan record.
    """
    wrapper = _safe_regeneration_child_lease(wrapper_lease)
    if wrapper is None:
        return None
    protocol = _waterlily_progress_protocol_module()
    if protocol is None:
        return None
    try:
        pointer = protocol.read_active_run_record()
        if pointer.get("wrapper") != wrapper:
            return None
        updater = _safe_regeneration_child_lease(pointer.get("child"))
        if updater is None:
            return None
    except Exception:
        return None
    if _process_lease_liveness(updater) not in {"live", "stopped"}:
        return None
    return {"version": 1, "wrapper": wrapper, "updater": updater}


def _stored_regeneration_orphan(incident_path: Path) -> dict[str, Any] | None:
    """Read one already-adopted wrapper-to-updater handoff, if safe."""
    try:
        incident = json.loads(incident_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _safe_regeneration_orphan(
        incident.get("repair_regeneration_orphan") if isinstance(incident, dict) else None
    )


def _adopt_active_regeneration_orphan(
    incident_path: Path,
    wrapper_lease: Any,
) -> tuple[str, dict[str, Any] | None]:
    """Atomically retain a proven live updater after its wrapper disappears.

    A private-state lock can itself be temporarily unavailable.  In that
    case the live pointer is still sufficient to prohibit a replacement in
    this watchdog cycle; another cycle can persist it.  This deliberately
    favors one continuing report over an unsafe parallel regeneration.
    """
    wrapper = _safe_regeneration_child_lease(wrapper_lease)
    candidate = _active_regeneration_orphan_candidate(wrapper)
    if wrapper is None or candidate is None:
        return "unavailable", None
    outcome = "not_adopted"

    def predicate(payload: dict[str, Any]) -> bool:
        nonlocal outcome
        existing = _safe_regeneration_orphan(payload.get("repair_regeneration_orphan"))
        if existing is not None:
            outcome = "already_adopted" if existing == candidate else "conflicting_orphan"
            return False
        worker = payload.get("repair_worker")
        current_wrapper = _safe_regeneration_child_lease(
            worker.get("regeneration_child") if isinstance(worker, dict) else None
        )
        if current_wrapper != wrapper:
            # The original worker may have observed its wrapper exit just
            # before this CAS.  The proven live pointer still blocks a
            # replacement, but do not attach it to a newer worker/run.
            outcome = "live_unpersisted"
            return False
        # Re-read while holding the incident's narrow CAS lease so a newly
        # acquired scheduler wrapper cannot be confused with this one.
        if _active_regeneration_orphan_candidate(wrapper) != candidate:
            outcome = "unavailable"
            return False
        outcome = "adopted"
        return True

    try:
        changed, _payload = compare_and_update_private_json(
            incident_path,
            predicate,
            {"repair_regeneration_orphan": candidate},
        )
    except Exception:
        return "live_unpersisted", candidate
    if changed:
        return "adopted", candidate
    # A competing watchdog may already have attached the same exact handoff.
    if outcome == "already_adopted":
        return outcome, candidate
    # A currently live exact pointer must remain a no-replacement condition
    # even if an old worker record changed under us.
    return outcome, candidate


def _clear_regeneration_orphan(
    incident_path: Path,
    orphan: Any,
) -> bool:
    """Clear only the exact adopted updater after it has definitely exited."""
    expected = _safe_regeneration_orphan(orphan)
    if expected is None:
        return False
    try:
        changed, _payload = compare_and_update_private_json(
            incident_path,
            lambda payload: _safe_regeneration_orphan(payload.get("repair_regeneration_orphan")) == expected,
            {"repair_regeneration_orphan": None},
        )
    except Exception:
        return False
    return changed


def _waterlily_progress_protocol_module() -> Any | None:
    """Load the allowlisted Waterlily progress protocol, never arbitrary code.

    The Vessence watchdog deliberately does not scan a directory for the
    newest marker.  It reads the one wrapper-owned active pointer through the
    protocol that validates exact fields, permissions, nonce binding, and
    allowed phase names.  Import errors are treated as unavailable evidence,
    never as a reason to kill a live report.
    """
    source = _waterlily_project_root() / "scripts" / "nightly_progress.py"
    if not source.is_file():
        return None
    try:
        # ``nightly_progress`` defines dataclasses.  Their decorator resolves
        # ``sys.modules[cls.__module__]`` while the module body is executing,
        # so a bare ``module_from_spec``/``exec_module`` import makes every
        # Vessence-side liveness read silently unavailable.  Use one private,
        # stable name and register it before execution; restore an existing
        # module if this allowlisted import fails.
        module_name = "_vessence_waterlily_nightly_progress_protocol"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        previous_module = sys.modules.get(module_name)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            if previous_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module
            return None
        expected_root = (VESSENCE_DATA_HOME / WATERLILY_NIGHTLY_PROGRESS_RELATIVE).resolve()
        protocol_root = Path(module.PROGRESS_ROOT).resolve()
        if protocol_root != expected_root:
            return None
        return module
    except Exception:
        return None


def _active_waterlily_run_pointer_liveness() -> dict[str, Any] | None:
    """Return minimal proof of a live active-run pointer, if any.

    This is a read-only guardian for legacy wrappers that started before a
    repair incident recorded its regeneration-child lease.  It deliberately
    does not infer a hang from a marker, elapsed time, or source output, and
    it never signals a process.  A valid exact wrapper/updater lease is enough
    to prevent an overlapping repair from launching beside the active report.
    """
    protocol = _waterlily_progress_protocol_module()
    if protocol is None:
        return None
    try:
        pointer = protocol.read_active_run_record()
        wrapper = _safe_regeneration_child_lease(pointer.get("wrapper"))
        child = _safe_regeneration_child_lease(pointer.get("child"))
        nonce = str(pointer.get("run_nonce") or "")
    except Exception:
        return None
    if wrapper is None or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        return None
    wrapper_state = _process_lease_liveness(wrapper)
    child_state = _process_lease_liveness(child) if child is not None else "none"
    if wrapper_state not in {"live", "stopped"} and child_state not in {"live", "stopped"}:
        return None
    return {
        "version": 1,
        "run_nonce": nonce,
        "wrapper": wrapper,
        "child": child,
    }


def _ordinary_waterlily_orphan_candidate() -> dict[str, Any] | None:
    """Prove an ordinary scheduler wrapper died around one live updater.

    This closes the legacy/ordinary-cron hole: a wrapper can die after it
    creates the separately sessioned updater, leaving the updater's inherited
    scheduler flock held forever.  We require the private pointer's exact
    wrapper/child leases, a dead wrapper, a live isolated updater group, and
    the still-held scheduler lock.  Anything missing or ambiguous is a strict
    no-action state rather than a reason to signal a process.
    """
    pointer = _active_waterlily_run_pointer_liveness()
    if pointer is None:
        return None
    wrapper = _safe_regeneration_child_lease(pointer.get("wrapper"))
    child = _safe_regeneration_child_lease(pointer.get("child"))
    if wrapper is None or child is None:
        return None
    if _process_lease_liveness(wrapper) not in {"lost", "reused"}:
        return None
    if _process_lease_liveness(child) != "live":
        return None
    # A caller may ultimately signal only an updater that owns its own
    # process group.  Verify this before an incident/watchdog state exists.
    if _verified_regeneration_child_group(child) != int(child["pid"]):
        return None
    if not _waterlily_scheduler_lock_is_held():
        return None
    candidate = _active_regeneration_orphan_candidate(wrapper)
    if candidate is None or candidate.get("updater") != child:
        return None
    # Re-read the pointer/leases immediately before durable adoption.  A
    # replacement nightly run must never be attached to the dead wrapper.
    latest = _active_waterlily_run_pointer_liveness()
    if latest is None or latest.get("wrapper") != wrapper or latest.get("child") != child:
        return None
    if _process_lease_liveness(wrapper) not in {"lost", "reused"}:
        return None
    if _process_lease_liveness(child) != "live":
        return None
    return candidate


def _incident_path_from_capture(capture: Any) -> Path | None:
    """Accept only a durable incident path below the private incident root."""
    if not isinstance(capture, dict):
        return None
    raw = str(capture.get("incident_path") or "").strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser().resolve()
        root = INCIDENT_DIR.resolve()
    except Exception:
        return None
    if path.parent != root or not path.is_file():
        return None
    return path


def _attach_ordinary_waterlily_orphan(
    incident_path: Path,
    candidate: dict[str, Any],
) -> bool:
    """Durably attach only the same still-proven ordinary orphan updater."""
    expected = _safe_regeneration_orphan(candidate)
    if expected is None:
        return False

    def predicate(payload: dict[str, Any]) -> bool:
        existing = _safe_regeneration_orphan(payload.get("repair_regeneration_orphan"))
        if existing == expected:
            return False
        if existing is not None:
            return False
        return _ordinary_waterlily_orphan_candidate() == expected

    try:
        changed, payload = compare_and_update_private_json(
            incident_path,
            predicate,
            {"repair_regeneration_orphan": expected},
        )
    except Exception:
        return False
    return changed or _safe_regeneration_orphan(payload.get("repair_regeneration_orphan")) == expected


def _incident_owns_active_waterlily_pointer(
    incident: dict[str, Any],
    pointer: dict[str, Any],
) -> bool:
    """Return whether this incident already durably owns that exact pointer."""
    wrapper = _safe_regeneration_child_lease(pointer.get("wrapper"))
    child = _safe_regeneration_child_lease(pointer.get("child"))
    if wrapper is None:
        return False
    worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else {}
    if _safe_regeneration_child_lease(worker.get("regeneration_child")) == wrapper:
        return True
    orphan = _safe_regeneration_orphan(incident.get("repair_regeneration_orphan"))
    return bool(
        orphan is not None
        and orphan["wrapper"] == wrapper
        and child is not None
        and orphan["updater"] == child
    )


def _read_waterlily_regeneration_progress_for_pointer(
    wrapper_lease: Any,
    *,
    updater_lease: Any | None = None,
) -> dict[str, Any] | None:
    """Read aggregate liveness only for one exact wrapper/updater pointer.

    ``updater_lease`` is supplied only after an unexpected wrapper death.
    In that case both process identities must still match the private pointer
    before a direct updater signal is even considered.  The normal wrapper
    path leaves it ``None`` and keeps the wrapper's graceful forwarding
    behavior.
    """
    expected_wrapper = _safe_regeneration_child_lease(wrapper_lease)
    expected_updater = (
        None if updater_lease is None else _safe_regeneration_child_lease(updater_lease)
    )
    if expected_wrapper is None or (updater_lease is not None and expected_updater is None):
        return None
    protocol = _waterlily_progress_protocol_module()
    if protocol is None:
        return None
    try:
        pointer = protocol.read_active_run_record()
        if pointer.get("wrapper") != expected_wrapper:
            return None
        pointer_updater = _safe_regeneration_child_lease(pointer.get("child"))
        if pointer_updater is None:
            return None
        if expected_updater is not None and pointer_updater != expected_updater:
            return None
        nonce = str(pointer.get("run_nonce") or "")
        marker = protocol.read_progress_record(
            protocol.progress_path_for_nonce(nonce),
            expected_nonce=nonce,
        )
        # Sequence 1 is the wrapper's pre-Popen bootstrap marker. It proves
        # only that an isolated child *can* inherit the protocol, not that the
        # updater actually acknowledged it. Do not terminate until the child
        # has emitted its first real boundary at sequence >= 2.
        if int(marker.get("seq") or 0) <= 1:
            return None
        stalled = bool(protocol.progress_is_stalled(marker))
    except Exception:
        return None
    phase = str(marker.get("phase") or "")
    updated_at = str(marker.get("updated_at") or "")
    units_completed = marker.get("units_completed")
    sequence = marker.get("seq")
    if (
        not nonce
        or not phase
        or not updated_at
        or isinstance(units_completed, bool)
        or not isinstance(units_completed, int)
        or isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence <= 0
    ):
        return None
    return {
        "version": 1,
        "run_nonce": nonce,
        "seq": sequence,
        "phase": phase,
        "units_completed": units_completed,
        "updated_at": updated_at,
        "stalled": stalled,
    }


def _read_waterlily_regeneration_progress(lease: dict[str, Any]) -> dict[str, Any] | None:
    """Read one exact normal-wrapper marker and return aggregate liveness."""
    return _read_waterlily_regeneration_progress_for_pointer(lease)


def _read_orphaned_waterlily_regeneration_progress(
    orphan: Any,
) -> dict[str, Any] | None:
    """Read a marker only when an adopted wrapper-to-updater link still holds."""
    safe_orphan = _safe_regeneration_orphan(orphan)
    if safe_orphan is None:
        return None
    return _read_waterlily_regeneration_progress_for_pointer(
        safe_orphan["wrapper"],
        updater_lease=safe_orphan["updater"],
    )


def _safe_regeneration_watchdog_state(value: Any) -> dict[str, Any] | None:
    """Accept only the finite state needed to deduplicate a graceful stop."""
    if not isinstance(value, dict):
        return None
    required = {
        "version",
        "state",
        "run_nonce",
        "pid",
        "start_ticks",
        "seq",
        "phase",
        "units_completed",
        "updated_at",
        "observed_at",
    }
    if set(value) != required or value.get("version") != 1:
        return None
    if value.get("state") not in {"candidate", "termination_requested"}:
        return None
    lease = _safe_regeneration_child_lease({"pid": value.get("pid"), "start_ticks": value.get("start_ticks")})
    if lease is None:
        return None
    nonce = value.get("run_nonce")
    phase = value.get("phase")
    updated_at = value.get("updated_at")
    observed_at = value.get("observed_at")
    if (
        not isinstance(nonce, str)
        or not re.fullmatch(r"[0-9a-f]{32}", nonce)
        or not isinstance(phase, str)
        or not phase
        or not isinstance(updated_at, str)
        or not _parse_iso(updated_at)
        or not isinstance(observed_at, str)
        or not _parse_iso(observed_at)
    ):
        return None
    seq = value.get("seq")
    units = value.get("units_completed")
    if (
        isinstance(seq, bool)
        or not isinstance(seq, int)
        or seq <= 0
        or isinstance(units, bool)
        or not isinstance(units, int)
        or units < 0
    ):
        return None
    return {
        "version": 1,
        "state": str(value["state"]),
        "run_nonce": nonce,
        **lease,
        "seq": seq,
        "phase": phase,
        "units_completed": units,
        "updated_at": updated_at,
        "observed_at": observed_at,
    }


def _regeneration_watchdog_observation(lease: dict[str, Any], progress: dict[str, Any], *, state: str) -> dict[str, Any]:
    """Create a safe, exact state record from an already validated marker."""
    safe_lease = _safe_regeneration_child_lease(lease)
    if safe_lease is None:
        raise ValueError("regeneration child lease is invalid")
    return {
        "version": 1,
        "state": state,
        "run_nonce": str(progress["run_nonce"]),
        **safe_lease,
        "seq": int(progress["seq"]),
        "phase": str(progress["phase"]),
        "units_completed": int(progress["units_completed"]),
        "updated_at": str(progress["updated_at"]),
        "observed_at": _iso(),
    }


def _same_regeneration_progress(state: dict[str, Any], lease: dict[str, Any], progress: dict[str, Any]) -> bool:
    return (
        state.get("run_nonce") == progress.get("run_nonce")
        and state.get("pid") == lease.get("pid")
        and state.get("start_ticks") == lease.get("start_ticks")
        and state.get("seq") == progress.get("seq")
        and state.get("phase") == progress.get("phase")
        and state.get("units_completed") == progress.get("units_completed")
        and state.get("updated_at") == progress.get("updated_at")
    )


def _reset_regeneration_termination_intent(
    incident_path: Path,
    lease: dict[str, Any],
    progress: dict[str, Any],
) -> None:
    """Allow a later proven stall if the just-before-signal check advanced."""
    candidate = _regeneration_watchdog_observation(lease, progress, state="candidate")

    def predicate(payload: dict[str, Any]) -> bool:
        state = _safe_regeneration_watchdog_state(payload.get("repair_regeneration_watchdog"))
        return bool(state and state.get("state") == "termination_requested" and _same_regeneration_progress(state, lease, progress))

    try:
        compare_and_update_private_json(
            incident_path,
            predicate,
            {"repair_regeneration_watchdog": candidate},
        )
    except Exception:
        pass


def _verified_regeneration_child_group(lease: dict[str, Any]) -> int | None:
    """Return an isolated child PGID only after a final PID/tick recheck."""
    safe_lease = _safe_regeneration_child_lease(lease)
    if safe_lease is None:
        return None
    observed = _process_start_ticks_and_state(int(safe_lease["pid"]))
    if observed is None:
        return None
    start_ticks, state = observed
    pid = int(safe_lease["pid"])
    if start_ticks != safe_lease["start_ticks"] or state.upper() in {"Z", "T"}:
        return None
    try:
        if os.getpgid(pid) != pid:
            return None
    except OSError:
        return None
    return pid


def _observe_stalled_regeneration_with_reader(
    incident_path: Path,
    lease: dict[str, Any],
    read_progress: Callable[[], dict[str, Any] | None],
) -> str:
    """Request one graceful stop only after two identical stale observations.

    This is intentionally operation-based: it examines an unchanged
    nonce/sequence/phase/unit marker past that phase's allowance.  It never
    uses report elapsed time, worker heartbeat age, log text, source content,
    or a kill escalation.  Missing or malformed progress evidence is a
    no-action state, not proof a live report is stuck.
    """
    progress = read_progress()
    if progress is None:
        return "protocol_unavailable"
    if not progress.get("stalled"):
        return "progressing"
    transition = "candidate"
    candidate = _regeneration_watchdog_observation(lease, progress, state="candidate")
    intent = _regeneration_watchdog_observation(lease, progress, state="termination_requested")

    def predicate(payload: dict[str, Any]) -> bool:
        nonlocal transition
        existing = _safe_regeneration_watchdog_state(payload.get("repair_regeneration_watchdog"))
        if existing and existing.get("state") == "termination_requested":
            if existing.get("pid") == lease.get("pid") and existing.get("start_ticks") == lease.get("start_ticks"):
                transition = "already_requested"
                return False
        if existing and existing.get("state") == "candidate" and _same_regeneration_progress(existing, lease, progress):
            transition = "request"
            return True
        transition = "candidate"
        return True

    try:
        changed, _payload = compare_and_update_private_json(
            incident_path,
            predicate,
            lambda _payload: {
                "repair_regeneration_watchdog": intent if transition == "request" else candidate,
            },
        )
    except Exception:
        return "state_unavailable"
    if not changed:
        return transition
    if transition != "request":
        return "candidate"

    # The marker can advance between the first observation and the compare-
    # and-set.  Re-read it immediately before a signal.  A change cancels the
    # request rather than taking a chance on a healthy long-running phase.
    final_progress = read_progress()
    if final_progress is None or not final_progress.get("stalled") or not _same_regeneration_progress(intent, lease, final_progress):
        _reset_regeneration_termination_intent(incident_path, lease, progress)
        return "progressing"
    pgid = _verified_regeneration_child_group(lease)
    if pgid is None:
        _reset_regeneration_termination_intent(incident_path, lease, progress)
        return "child_revalidation_failed"
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        _reset_regeneration_termination_intent(incident_path, lease, progress)
        return "signal_failed"
    return "termination_requested"


def _observe_stalled_regeneration_child(incident_path: Path, lease: dict[str, Any]) -> str:
    """Observe a normal wrapper and let it relay a verified graceful stop."""
    return _observe_stalled_regeneration_with_reader(
        incident_path,
        lease,
        lambda: _read_waterlily_regeneration_progress(lease),
    )


def _observe_stalled_orphaned_regeneration(
    incident_path: Path,
    orphan: Any,
) -> str:
    """Observe a verified orphan updater and signal only its own group."""
    safe_orphan = _safe_regeneration_orphan(orphan)
    if safe_orphan is None:
        return "protocol_unavailable"
    updater = safe_orphan["updater"]
    return _observe_stalled_regeneration_with_reader(
        incident_path,
        updater,
        lambda: _read_orphaned_waterlily_regeneration_progress(safe_orphan),
    )


def _stored_regeneration_child_lease(incident_path: Path) -> dict[str, Any] | None:
    try:
        incident = json.loads(incident_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    worker = incident.get("repair_worker") if isinstance(incident, dict) else None
    return _safe_regeneration_child_lease(
        worker.get("regeneration_child") if isinstance(worker, dict) else None
    )


def _stored_provider_child_lease(incident_path: Path) -> dict[str, Any] | None:
    """Read only a structurally valid provider lease from durable state."""
    try:
        incident = json.loads(incident_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    worker = incident.get("repair_worker") if isinstance(incident, dict) else None
    return _safe_provider_child_lease(
        worker.get("provider_child") if isinstance(worker, dict) else None
    )


def _update_repair_worker(
    incident_path: Path,
    *,
    phase: str,
    phase_attempt: int | None = None,
    progress: bool = False,
    regeneration_child: dict[str, Any] | None | object = _UNCHANGED,
    provider_child: dict[str, Any] | None | object = _UNCHANGED,
) -> bool:
    """Persist a privacy-safe worker heartbeat/phase for watchdog recovery."""
    observed = _process_start_ticks_and_state(os.getpid())
    if observed is None:
        return False
    start_ticks, _state = observed
    now = _iso()
    worker: dict[str, Any] = {
        "pid": os.getpid(),
        "start_ticks": start_ticks,
        "phase": str(phase or "unknown"),
        "heartbeat_at": now,
    }
    if phase_attempt is not None:
        worker["phase_attempt"] = max(0, int(phase_attempt))
    if progress:
        worker["progress_at"] = now
    if regeneration_child is _UNCHANGED:
        existing_child = _stored_regeneration_child_lease(incident_path)
        if existing_child is not None:
            worker["regeneration_child"] = existing_child
    elif regeneration_child is not None:
        child = _safe_regeneration_child_lease(regeneration_child)
        if child is not None:
            worker["regeneration_child"] = child
    if provider_child is _UNCHANGED:
        existing_provider = _stored_provider_child_lease(incident_path)
        if existing_provider is not None:
            worker["provider_child"] = existing_provider
    elif provider_child is not None:
        provider = _safe_provider_child_lease(provider_child)
        if provider is not None:
            worker["provider_child"] = provider
    return _write_incident_update(incident_path, repair_worker=worker)


def _heartbeat_active_repair_worker(*, phase: str, phase_attempt: int | None = None) -> bool:
    path = _ACTIVE_REPAIR_INCIDENT_PATH
    if path is None:
        return False
    return _update_repair_worker(path, phase=phase, phase_attempt=phase_attempt)


def _set_repair_regeneration_child(
    incident_path: Path,
    *,
    pid: int,
    phase: str,
    phase_attempt: int,
) -> bool:
    """Persist the child that may outlive a crashed repair parent."""
    observed = _process_start_ticks_and_state(pid)
    if observed is None:
        return False
    start_ticks, _state = observed
    return _update_repair_worker(
        incident_path,
        phase=phase,
        phase_attempt=phase_attempt,
        progress=True,
        regeneration_child={"pid": int(pid), "start_ticks": start_ticks},
    )


def _clear_repair_regeneration_child(
    incident_path: Path,
    *,
    phase: str,
    phase_attempt: int,
) -> bool:
    """Clear a reaped child's lease while retaining the parent worker lease."""
    return _update_repair_worker(
        incident_path,
        phase=phase,
        phase_attempt=phase_attempt,
        regeneration_child=None,
    )


def _set_repair_provider_child(
    incident_path: Path,
    *,
    provider: str,
    pid: int,
    phase: str,
    phase_attempt: int,
) -> bool:
    """Persist the exact provider process before it can edit the checkout.

    This is called synchronously from the CLI wrapper immediately after
    ``Popen``.  Returning ``False`` makes that wrapper gracefully terminate
    only the just-created process group, so an untracked Codex/Claude can
    never overlap a resumed repair worker.
    """
    provider_name = str(provider or "").strip().lower()
    if provider_name not in _CRITICAL_REPAIR_PROVIDERS:
        return False
    observed = _process_start_ticks_and_state(pid)
    if observed is None:
        return False
    start_ticks, _state = observed
    return _update_repair_worker(
        incident_path,
        phase=phase,
        phase_attempt=phase_attempt,
        progress=True,
        provider_child={
            "provider": provider_name,
            "pid": int(pid),
            "start_ticks": start_ticks,
        },
    )


def _clear_repair_provider_child(
    incident_path: Path,
    *,
    phase: str,
    phase_attempt: int,
) -> bool:
    """Clear a reaped provider lease only for this exact repair worker.

    A terminal path can clear ``repair_worker`` before Python unwinds a
    provider-call ``finally`` block.  A generic merge at that point would
    accidentally resurrect the worker lease.  The compare-and-set below makes
    an already-finished/replaced worker a safe no-op instead.
    """
    observed = _process_start_ticks_and_state(os.getpid())
    if observed is None:
        return False
    start_ticks, _state = observed
    now = _iso()

    def predicate(payload: dict[str, Any]) -> bool:
        worker = payload.get("repair_worker")
        return bool(
            isinstance(worker, dict)
            and int(worker.get("pid") or 0) == os.getpid()
            and str(worker.get("start_ticks") or "") == start_ticks
        )

    def updates(payload: dict[str, Any]) -> dict[str, Any]:
        worker = dict(payload["repair_worker"])
        worker.pop("provider_child", None)
        worker["phase"] = str(phase or "unknown")
        worker["phase_attempt"] = max(0, int(phase_attempt))
        worker["heartbeat_at"] = now
        return {"repair_worker": worker}

    try:
        changed, _payload = compare_and_update_private_json(incident_path, predicate, updates)
    except Exception:
        return False
    return changed


def _wait_for_orphaned_regeneration_updater(
    incident_path: Path,
    orphan: Any,
    *,
    phase: str,
    phase_attempt: int,
) -> str:
    """Retain the repair lease while a proven updater outlives its wrapper.

    The updater is no longer a direct ``Popen`` child of this worker, so it
    cannot be reaped here.  Its exact PID/start-tick lease and the active
    pointer are enough to wait safely without a wall-clock deadline.  A
    malformed progress marker merely disables a signal; it never authorizes a
    second report or a broad process search.
    """
    safe_orphan = _safe_regeneration_orphan(orphan)
    if safe_orphan is None:
        return "unavailable"
    updater = safe_orphan["updater"]
    while True:
        state = _process_lease_liveness(updater)
        if state == "live":
            _heartbeat_active_repair_worker(phase=phase, phase_attempt=phase_attempt)
            _observe_stalled_orphaned_regeneration(incident_path, safe_orphan)
            time.sleep(_repair_worker_heartbeat_interval())
            continue
        if state == "stopped":
            # Keep the project lease while a stopped report is resumed.  A
            # failed SIGCONT is not permission to launch another updater.
            try:
                os.kill(int(updater["pid"]), signal.SIGCONT)
            except (OSError, TypeError, ValueError):
                pass
            _heartbeat_active_repair_worker(phase=phase, phase_attempt=phase_attempt)
            time.sleep(_repair_worker_heartbeat_interval())
            continue
        return state


def _wait_for_scheduler_lock_release(*, phase: str, phase_attempt: int) -> None:
    """Wait for an unidentifiable inherited nightly lock without timing out.

    This covers only the narrow wrapper-Popen-to-pointer-attachment crash
    window.  We deliberately do not scan process arguments or signal an
    unknown lock holder.  Once it releases, the normal summary verifier
    decides whether another repair attempt is actually necessary.
    """
    while _waterlily_scheduler_lock_is_held():
        _heartbeat_active_repair_worker(phase=phase, phase_attempt=phase_attempt)
        time.sleep(_repair_worker_heartbeat_interval())


def _clear_repair_worker(incident_path: Path) -> bool:
    """Release the durable lease when this process reaches a known exit path."""
    return _write_incident_update(
        incident_path,
        repair_worker=None,
        repair_worker_finished_at=_iso(),
    )


def _append_repair_failure_announcement(
    path: Path,
    task_id: str,
    message: str,
    created_at: str,
) -> bool:
    """Append one safe in-app Vessence message without importing web at boot."""
    from jane_web.task_offloader_announcements import append_task_progress_announcement_once

    return append_task_progress_announcement_once(path, task_id, message, created_at, final=True)


def _repair_provider_failure_task_id(incident: dict[str, Any], incident_path: Path) -> str:
    """Use a stable per-incident ID so only retries of that file dedupe.

    Incident IDs intentionally derive from a failure fingerprint.  A later
    recurrence may therefore have the same ID but a different durable incident
    file and needs a fresh Vessence alert after Codex and Claude both exhaust.
    """
    try:
        path_identity = str(Path(incident_path).resolve())
    except Exception:
        path_identity = str(incident_path)
    raw = f"{str(incident.get('id') or 'unknown')}\n{path_identity}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"self-healing-provider-failure-{digest}"


def _notify_repair_provider_exhaustion(
    incident_path: Path,
    incident: dict[str, Any],
    *,
    critical_waterlily: bool,
) -> bool:
    """Tell Chieh once when the deliberate Codex -> Claude handoff is spent.

    The incident lock serializes workers for one incident, and the persisted
    marker additionally prevents a watchdog restart from adding another
    announcement.  Failure to append is deliberately retried on the next
    provider-exhaustion cycle rather than marking an undelivered alert done.
    """
    try:
        persisted = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        persisted = incident
    if not isinstance(persisted, dict):
        persisted = incident
    if (
        persisted.get("repair_provider_exhaustion_notification_state") == "sent"
        or persisted.get("repair_provider_exhaustion_notified_at")
    ):
        return False

    created_at = str(persisted.get("repair_provider_exhaustion_notification_created_at") or _iso())
    task_id = str(
        persisted.get("repair_provider_exhaustion_notification_task_id")
        or _repair_provider_failure_task_id(incident, incident_path)
    )
    message = (
        REPAIR_PROVIDER_FAILURE_MESSAGE
        if critical_waterlily
        else GENERIC_REPAIR_PROVIDER_FAILURE_MESSAGE
    )
    # Persist intent first.  A crash after the append but before ``sent`` is
    # resolved by the stable-ID append-once writer on the next watchdog retry.
    if not _write_incident_update(
        incident_path,
        repair_provider_exhaustion_notification_state="pending",
        repair_provider_exhaustion_notification_task_id=task_id,
        repair_provider_exhaustion_notification_created_at=created_at,
    ):
        return False
    try:
        _append_repair_failure_announcement(
            VESSENCE_DATA_HOME / "data" / "jane_announcements.jsonl",
            task_id,
            message,
            created_at,
        )
    except Exception:
        return False
    return _write_incident_update(
        incident_path,
        repair_provider_exhaustion_notification_state="sent",
        repair_provider_exhaustion_notified_at=created_at,
        repair_provider_exhaustion_notification_task_id=task_id,
    )


def _is_repair_providers_exhausted(exc: BaseException) -> bool:
    """Avoid coupling recovery startup to the CLI wrapper at module import."""
    from agent_skills.claude_cli_llm import RepairProvidersExhausted

    return isinstance(exc, RepairProvidersExhausted)


def _critical_waterlily_nightly_incident(incident: dict[str, Any], project_root: Path) -> bool:
    tags = {str(tag) for tag in incident.get("tags") or []}
    payload = incident.get("payload") if isinstance(incident.get("payload"), dict) else {}
    return (
        project_root == _waterlily_project_root()
        and str(incident.get("source") or "") == WATERLILY_NIGHTLY_SOURCE
        and (
            "critical-auto-repair" in tags
            or str(payload.get("auto_repair_priority") or "").lower() == "critical"
        )
    )


def _safe_retry_context(outcome: dict[str, Any] | None) -> dict[str, Any]:
    """Keep retry evidence structural: no source rows, logs, or runner prose."""
    if not isinstance(outcome, dict):
        return {}
    allowed = {
        "attempt",
        "kind",
        "error_type",
        "returncode",
        "summary_status",
        "summary_year",
        "summary_month",
        "summary_mode",
        "expected_income_reports",
        "verified_income_reports",
        "recovery_preflight",
        "summary_fresh",
        "verification_reason",
    }
    safe = {key: outcome[key] for key in allowed if key in outcome}
    provider = str(outcome.get("provider") or "").strip().lower()
    if provider in _CRITICAL_REPAIR_PROVIDERS:
        safe["provider"] = provider
    next_provider = str(outcome.get("next_provider") or "").strip().lower()
    if next_provider in _CRITICAL_REPAIR_PROVIDERS:
        safe["next_provider"] = next_provider
    cycle = outcome.get("provider_cycle")
    if isinstance(cycle, (list, tuple)):
        safe_cycle = [
            provider
            for provider in (str(item or "").strip().lower() for item in cycle)
            if provider in _CRITICAL_REPAIR_PROVIDERS
        ]
        if safe_cycle:
            safe["provider_cycle"] = sorted(set(safe_cycle))
    failure = outcome.get("nightly_failure")
    if isinstance(failure, dict):
        safe_failure: dict[str, Any] = {}
        if failure.get("summary_status") == "failed":
            safe_failure["summary_status"] = "failed"
        mode = str(failure.get("mode") or "")
        if mode in _SAFE_NIGHTLY_RECOVERY_MODES:
            safe_failure["mode"] = mode
        for key, lower, upper in (("year", 2000, 2100), ("month", 1, 12)):
            value = failure.get(key)
            if isinstance(value, int) and lower <= value <= upper:
                safe_failure[key] = value
        raw_canaries = failure.get("canaries")
        if isinstance(raw_canaries, list):
            canaries: list[dict[str, Any]] = []
            for raw in raw_canaries:
                if not isinstance(raw, dict):
                    continue
                kind = str(raw.get("kind") or "")
                if kind not in _SAFE_NIGHTLY_CANARY_FIELDS:
                    continue
                entry: dict[str, Any] = {"kind": kind}
                status = str(raw.get("status") or "")
                if status in {"failed", "passed", "initialized"}:
                    entry["status"] = status
                version = raw.get("profile_version")
                if isinstance(version, int) and 0 < version <= 1000:
                    entry["profile_version"] = version
                format_hash = str(raw.get("format_hash") or "")
                if re.fullmatch(r"[a-f0-9]{16,64}", format_hash):
                    entry["format_hash"] = format_hash
                canaries.append(entry)
            if canaries:
                safe_failure["canaries"] = canaries
        if safe_failure:
            safe["nightly_failure"] = safe_failure
    return safe


def _provider_cycle_state(incident: dict[str, Any]) -> tuple[set[str], str]:
    """Read only the durable Codex/Claude end-to-end failure state."""
    raw_cycle = incident.get("repair_provider_cycle")
    cycle = {
        str(provider or "").strip().lower()
        for provider in (raw_cycle if isinstance(raw_cycle, (list, tuple)) else [])
        if str(provider or "").strip().lower() in _CRITICAL_REPAIR_PROVIDERS
    }
    next_provider = str(incident.get("repair_next_provider") or "").strip().lower()
    if next_provider not in _CRITICAL_REPAIR_PROVIDERS:
        next_provider = "claude" if cycle == {"codex"} else "codex"
    return cycle, next_provider


def _provider_order_for_attempt(cycle: set[str], next_provider: str) -> tuple[str, ...]:
    """Try a full Codex→Claude handoff only at the start of a fresh cycle."""
    if next_provider == "claude":
        return ("claude",)
    if not cycle:
        return ("codex", "claude")
    return ("codex",)


def _advance_provider_cycle(
    cycle: set[str],
    failed_providers: tuple[str, ...] | list[str] | set[str],
) -> tuple[set[str], str, bool]:
    """Record end-to-end provider failures and decide the next safe handoff.

    ``exhausted`` means both approved providers have failed in this durable
    cycle.  The caller alerts Chieh once and resets to Codex for future retry;
    this never falls through to Gemini or abandons the incident.
    """
    next_cycle = set(cycle)
    next_cycle.update(
        str(provider or "").strip().lower()
        for provider in failed_providers
        if str(provider or "").strip().lower() in _CRITICAL_REPAIR_PROVIDERS
    )
    exhausted = _CRITICAL_REPAIR_PROVIDERS.issubset(next_cycle)
    if exhausted:
        return set(), "codex", True
    return next_cycle, ("claude" if "codex" in next_cycle else "codex"), False


def _build_prompt(
    incident: dict[str, Any],
    incident_path: Path,
    project_root: Path,
    *,
    retry_context: dict[str, Any] | None = None,
) -> str:
    source = incident.get("source", "")
    logs = _collect_log_context(str(source), project_root)
    incident_json = json.dumps(incident, indent=2, sort_keys=True)
    retry_json = json.dumps(_safe_retry_context(retry_context), indent=2, sort_keys=True)
    return f"""You are Jane's self-healing repair runner.

Chieh wants Vessence and the education website to be robust and self-healing:
when an error is captured, Jane should inspect it manually, understand the
evidence, and fix the underlying issue when safe.

Incident file: {incident_path}
Project root: {project_root}
Source: {source}

Rules:
- Follow the project instructions in AGENTS.md or CLAUDE.md.
- Query Jane memory if the project instructions require it or if project history matters.
- Diagnose from evidence: read relevant source, logs, configs, and runtime state before explaining a cause.
- Do not revert unrelated dirty work. Preserve user changes.
- Before editing source code, inspect the shared coordination board and post
  this repair with file-scoped claims using
  `/home/chieh/ambient/vessence/agent_skills/code_coordination.py`. Do not edit
  through another task's claim; choose non-overlapping work or report the
  conflict. Close the board task after verification.
- Prefer the smallest fix that addresses the captured failure.
- Add or run focused tests when feasible. If tests are blocked, explain exactly why.
- Do not deploy, restart production services, delete data, rotate secrets, or run destructive commands.
- If the issue is transient, external, credential-related, CAPTCHA/MFA-related, or otherwise unsafe to patch automatically, write a clear report and stop.
- If this is a web/UI automation failure, inspect the page, DOM, screenshots, logs, or downloaded artifacts and adapt the flow rather than stopping at a stale selector.
- Never approve or refresh a Waterlily AcuBliss/DASYS UI-format baseline from
  this autonomous repair. A detected format change requires a reviewed
  structural profile and the separate global code-edit lock approval path;
  fix selectors/contracts when evidence supports it, otherwise report the
  review requirement.
- LLM runner fallback policy: use Codex/OpenAI first; if Codex is unavailable,
  token-full, quota-limited, timed out, or otherwise fails, use Claude Code next.
  If Claude Code also fails, the repair runner must record the safe failure,
  notify Chieh through Vessence, and keep critical Waterlily retries active.
- Waterlily privacy guard: never send or quote patient names, accounting rows,
  downloaded artifact contents, credentials, cookies, or screenshots with
  patient data. Use only the sanitized incident and safe structural evidence.

Incident JSON:
```json
{incident_json}
```

Prior repair/regeneration outcome (safe structural fields only):
```json
{retry_json}
```

Recent logs:
```text
{logs}
```

Complete the repair end to end if safe. Finish with a concise report including:
1. definite cause or evidence checked,
2. files changed,
3. verification commands and results,
4. any remaining risk or blocker.
"""


def _positive_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _repair_attempt_timeout() -> int:
    # Preserve the old environment setting while making its scope explicit:
    # this is one provider attempt, never a terminal repair deadline.
    old_name = os.environ.get("JANE_SELF_HEAL_REPAIR_TIMEOUT_SEC", "1800")
    try:
        legacy_timeout = int(old_name)
    except (TypeError, ValueError):
        legacy_timeout = 1800
    return _positive_int_env("JANE_SELF_HEAL_REPAIR_ATTEMPT_TIMEOUT_SEC", legacy_timeout)


def _retry_delay_seconds(attempt: int) -> int:
    base = _positive_int_env("JANE_SELF_HEAL_REPAIR_RETRY_DELAY_SEC", 30)
    maximum = _positive_int_env("JANE_SELF_HEAL_REPAIR_RETRY_MAX_DELAY_SEC", 900)
    return min(maximum, base * (2 ** min(max(0, attempt - 1), 5)))


def _regeneration_timeout() -> int | None:
    """Never impose a wall-clock deadline on a verified report regeneration.

    A provider attempt may fail and hand off from Codex to Claude, but the
    actual Waterlily repair/regeneration must keep working until it reaches a
    verified result.  Ignore the legacy environment knob rather than allowing
    a deployment setting to silently reinstate an outer timeout.
    """
    return None


def _repair_worker_heartbeat_interval() -> int:
    """Bound only heartbeat cadence, never the regeneration itself."""
    return _positive_int_env("JANE_SELF_HEAL_WORKER_HEARTBEAT_SEC", 15)


def _job_path(incident: dict[str, Any]) -> Path | None:
    raw = str(incident.get("job_path") or "").strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser().resolve()
        queue_root = (VESSENCE_HOME / "configs" / "job_queue").resolve()
    except Exception:
        return None
    return path if path.parent == queue_root else None


def _set_job_status(incident: dict[str, Any], status: str, result_summary: str) -> None:
    path = _job_path(incident)
    if path is None or not path.is_file():
        return
    try:
        from agent_skills.job_queue_docs import set_status_content

        content = path.read_text(encoding="utf-8")
        updated = set_status_content(content, status, result_summary)
        path.write_text(updated, encoding="utf-8")
    except Exception:
        # Job bookkeeping must not prevent a successful report recovery.
        pass


def _parse_iso(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _expected_period(incident: dict[str, Any]) -> tuple[int | None, int | None]:
    payload = incident.get("payload") if isinstance(incident.get("payload"), dict) else {}
    year = payload.get("year")
    month = payload.get("month")
    return (year if isinstance(year, int) else None, month if isinstance(month, int) else None)


def _waterlily_recovery_preflight_args(incident: dict[str, Any]) -> tuple[str, ...]:
    """Return no autonomous UI-baseline approval commands.

    A baseline is an explicit trust decision about a vendor UI, not a repair
    side effect.  The worker may inspect a safe profile and fix broken
    extraction code, but must never turn a failed canary into a passing one by
    accepting the live format itself.  Keep this function as the allowlist
    boundary so future incident payload fields cannot smuggle approval flags
    into a regeneration command.
    """
    del incident
    return ()


_WATERLILY_NIGHTLY_PREFLIGHT_STEPS = frozenset({
    "acubliss_ui_canary",
    "acubliss_patient_notes_ui_canary",
    "acubliss_package_detail_ui_canary",
    "dasys_ui_canary",
    "dasys_payment_ui_canary",
    "dasys_files_ui_canary",
})
_SAFE_NIGHTLY_RECOVERY_MODES = frozenset({
    "incremental",
    "full",
    "acubliss_ui_format_baseline_refresh",
    "vendor_contract_baseline_refresh",
})
_SAFE_NIGHTLY_CANARY_FIELDS = (
    "acubliss_ui_canary",
    "acubliss_patient_notes_ui_canary",
    "acubliss_package_detail_ui_canary",
    "dasys_ui_canary",
    "dasys_payment_ui_canary",
    "dasys_files_ui_canary",
)


def _verify_waterlily_report_rebuild_evidence(
    data: dict[str, Any],
    *,
    summary_started_at: dt.datetime,
    require_full: bool = False,
) -> tuple[dict[str, int | str] | None, str]:
    """Prove an ``ok`` nightly summary actually rebuilt every income report.

    The runner's exit status and ``latest.json`` are necessary but not enough:
    a future control-flow regression could write ``status=ok`` after only a
    canary or source-sync phase.  Inspect only fixed step names, aggregate
    report counts, and timestamps.  Never retain practitioner names, source
    paths, rows, or report contents in a self-healing incident.
    """
    mode = str(data.get("mode") or "")
    if mode not in {"incremental", "full"}:
        return None, "summary_unsupported_mode"
    if require_full and mode != "full":
        # A repair begins because source extraction was untrusted. A rolling
        # incremental window cannot prove it re-fetched an earlier missing
        # current-month row, even if its cache rebuild/postflight succeeds.
        return None, "summary_recovery_not_full"

    raw_practitioners = data.get("practitioners")
    if not isinstance(raw_practitioners, list):
        return None, "summary_practitioners_invalid"
    practitioner_count = sum(1 for value in raw_practitioners if str(value or "").strip())
    if practitioner_count <= 0:
        return None, "summary_no_practitioners"

    steps = data.get("steps")
    if not isinstance(steps, list):
        return None, "summary_steps_invalid"
    typed_steps = [step for step in steps if isinstance(step, dict) and isinstance(step.get("type"), str)]
    step_types = {str(step["type"]) for step in typed_steps}
    if not _WATERLILY_NIGHTLY_PREFLIGHT_STEPS.issubset(step_types):
        return None, "summary_missing_ui_preflight"
    postflight = [step for step in typed_steps if step.get("type") == "semantic_postflight"]
    if len(postflight) != 1 or postflight[0].get("status") != "passed":
        return None, "summary_semantic_postflight_unverified"

    rebuild_type = "cache_rebuild" if mode == "incremental" else "full_current_month_refresh"
    income_type = "income" if mode == "incremental" else "income_full"
    error_type = "error_check" if mode == "incremental" else "error_check_full"
    rebuild_steps = [step for step in typed_steps if step.get("type") == rebuild_type]
    if len(rebuild_steps) != 1 or not isinstance(rebuild_steps[0].get("results"), list):
        return None, "summary_report_rebuild_missing"
    results = [result for result in rebuild_steps[0]["results"] if isinstance(result, dict)]
    result_types = [str(result.get("type") or "") for result in results]
    incomes = [result for result in results if result.get("type") == income_type]
    if len(incomes) != practitioner_count:
        return None, "summary_income_report_count_mismatch"
    if result_types.count(error_type) != 1 or result_types.count("total_income") != 1:
        return None, "summary_core_report_result_missing"
    if result_types.count("fsb_bank_error_check") != 1:
        return None, "summary_fsb_postflight_missing"

    generated_reports = [
        result
        for result in results
        if result.get("type") in {error_type, income_type, "total_income"}
    ]
    for result in generated_reports:
        generated_at = _parse_iso(result.get("generated_at"))
        if generated_at is None or generated_at < summary_started_at:
            return None, "summary_report_timestamp_unverified"

    return {
        "summary_mode": mode,
        "expected_income_reports": practitioner_count,
        "verified_income_reports": len(incomes),
    }, "verified"


def _safe_nightly_failure_handoff(
    summary_path: Path,
    *,
    previous_mtime_ns: int | None,
) -> dict[str, Any] | None:
    """Read only reviewed aggregate UI evidence after an active-repair failure.

    ``JANE_SELF_HEAL_ACTIVE`` correctly prevents the child from recursively
    creating another incident.  It must not also hide a newly observed UI
    drift from the next Codex/Claude attempt.  This deliberately accepts no
    exception string, source path, DOM text, patient data, or report rows.
    """
    try:
        stat = Path(summary_path).stat()
        data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    if previous_mtime_ns is not None and stat.st_mtime_ns <= previous_mtime_ns:
        return None
    if not isinstance(data, dict) or data.get("status") != "failed":
        return None
    observation: dict[str, Any] = {"summary_status": "failed"}
    mode = str(data.get("mode") or "")
    if mode in _SAFE_NIGHTLY_RECOVERY_MODES:
        observation["mode"] = mode
    year = data.get("year")
    month = data.get("month")
    if isinstance(year, int) and 2000 <= year <= 2100:
        observation["year"] = year
    if isinstance(month, int) and 1 <= month <= 12:
        observation["month"] = month
    canaries: list[dict[str, Any]] = []
    for field in _SAFE_NIGHTLY_CANARY_FIELDS:
        raw = data.get(field)
        if not isinstance(raw, dict):
            continue
        entry: dict[str, Any] = {"kind": field}
        status = str(raw.get("status") or "")
        if status in {"failed", "passed", "initialized"}:
            entry["status"] = status
        version = raw.get("profile_version")
        if isinstance(version, int) and 0 < version <= 1000:
            entry["profile_version"] = version
        format_hash = str(raw.get("format_hash") or "")
        if re.fullmatch(r"[a-f0-9]{16,64}", format_hash):
            entry["format_hash"] = format_hash
        # A finite canary kind alone is useful if its browser failure occurred
        # before a profile/hash could be collected.
        canaries.append(entry)
    if canaries:
        observation["canaries"] = canaries
    return observation


def _verify_waterlily_summary(
    summary_path: Path,
    *,
    incident: dict[str, Any],
    attempt_started_at: dt.datetime,
    previous_mtime_ns: int | None,
    require_full: bool = False,
) -> dict[str, Any]:
    """Return only safe proof that a new report generation actually succeeded."""
    outcome: dict[str, Any] = {"kind": "regeneration", "summary_fresh": False}
    try:
        stat = summary_path.stat()
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        outcome["verification_reason"] = "summary_unavailable"
        return outcome
    if not isinstance(data, dict):
        outcome["verification_reason"] = "summary_invalid"
        return outcome
    outcome.update({
        "summary_status": str(data.get("status") or ""),
        "summary_year": data.get("year") if isinstance(data.get("year"), int) else None,
        "summary_month": data.get("month") if isinstance(data.get("month"), int) else None,
    })
    if previous_mtime_ns is not None and stat.st_mtime_ns <= previous_mtime_ns:
        outcome["verification_reason"] = "summary_not_rewritten"
        return outcome
    generated = _parse_iso(data.get("started_at"))
    if generated is None or generated < attempt_started_at.replace(microsecond=0):
        outcome["verification_reason"] = "summary_stale"
        return outcome
    if data.get("status") != "ok":
        outcome["verification_reason"] = "summary_not_ok"
        return outcome
    if bool(data.get("dry_run")):
        outcome["verification_reason"] = "summary_dry_run"
        return outcome
    expected_year, expected_month = _expected_period(incident)
    if expected_year is not None and data.get("year") != expected_year:
        outcome["verification_reason"] = "summary_wrong_period"
        return outcome
    if expected_month is not None and data.get("month") != expected_month:
        outcome["verification_reason"] = "summary_wrong_period"
        return outcome
    rebuild_evidence, evidence_reason = _verify_waterlily_report_rebuild_evidence(
        data,
        summary_started_at=generated,
        require_full=require_full,
    )
    if rebuild_evidence is None:
        outcome["verification_reason"] = evidence_reason
        return outcome
    outcome.update(rebuild_evidence)
    outcome["summary_fresh"] = True
    outcome["verification_reason"] = "verified"
    return outcome


def _run_waterlily_regeneration(
    project_root: Path,
    incident: dict[str, Any],
    attempt: int,
    attempt_started_at: dt.datetime,
) -> dict[str, Any]:
    """Run reviewed recovery preflight plus wrapper and prove fresh reports."""
    script = project_root / WATERLILY_NIGHTLY_RUNNER
    summary_path = VESSENCE_DATA_HOME / WATERLILY_NIGHTLY_SUMMARY
    if project_root != _waterlily_project_root() or not script.is_file():
        return {"kind": "regeneration", "verification_reason": "allowlisted_runner_unavailable"}
    try:
        previous_mtime_ns = summary_path.stat().st_mtime_ns
    except OSError:
        previous_mtime_ns = None
    repair_log = LOG_DIR / "self_healing_regeneration" / f"{incident.get('id', 'incident')}-attempt-{attempt}.log"
    env = {
        **os.environ,
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
        # A failed verification is handled by this durable loop.  Do not spawn
        # a recursive incident/repair process for its own retry attempt.
        "JANE_SELF_HEAL_ACTIVE": "1",
    }
    # A repair can invoke a baseline preflight and a normal regeneration in
    # sequence.  Neither child may inherit an old marker from this worker's
    # environment; the scheduler wrapper mints one fresh nonce per child.
    env.pop("WATERLILY_NIGHTLY_PROGRESS_PATH", None)
    env.pop("WATERLILY_NIGHTLY_PROGRESS_NONCE", None)
    repair_log.parent.mkdir(parents=True, exist_ok=True)
    recovery_args = _waterlily_recovery_preflight_args(incident)
    recovery_preflight = (
        "acubliss_ui_format_baseline_refresh" if recovery_args else ""
    )

    def run_child(forwarded_args: tuple[str, ...], *, phase: str) -> tuple[int | None, str | None]:
        """Run one allowlisted wrapper invocation with no wall-clock cutoff."""
        try:
            with repair_log.open("a", encoding="utf-8") as handle:
                try:
                    repair_log.chmod(0o600)
                except OSError:
                    pass
                # Poll rather than imposing a deadline.  A living child
                # continues indefinitely, while the durable heartbeat makes
                # that fact visible to the five-minute watchdog after a parent
                # failure.  A new session separates child signal handling
                # from the repair worker itself.
                process = subprocess.Popen(
                    [PYTHON, str(script), *forwarded_args],
                    cwd=str(project_root),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                child_pid = getattr(process, "pid", None)
                child_leased = isinstance(child_pid, int) and child_pid > 0
                wrapper_lease: dict[str, Any] | None = None
                child_persisted = False
                if child_leased:
                    observed = _process_start_ticks_and_state(child_pid)
                    if observed is not None:
                        start_ticks, _state = observed
                        wrapper_lease = {"pid": int(child_pid), "start_ticks": start_ticks}
                    if _ACTIVE_REPAIR_INCIDENT_PATH is not None:
                        child_persisted = _set_repair_regeneration_child(
                            _ACTIVE_REPAIR_INCIDENT_PATH,
                            pid=child_pid,
                            phase=phase,
                            phase_attempt=attempt,
                        )
                try:
                    returncode: int | None = None
                    while returncode is None:
                        returncode = process.poll()
                        if returncode is not None:
                            # The wrapper is the direct child recorded in the
                            # incident, but it may have died after launching a
                            # still-live updater.  Adopt that updater before
                            # this finally block clears the wrapper lease, then
                            # keep this repair/project lease until it exits.
                            if wrapper_lease is not None and _ACTIVE_REPAIR_INCIDENT_PATH is not None:
                                adoption, orphan = _adopt_active_regeneration_orphan(
                                    _ACTIVE_REPAIR_INCIDENT_PATH,
                                    wrapper_lease,
                                )
                                if orphan is not None and adoption in {
                                    "adopted",
                                    "already_adopted",
                                    "live_unpersisted",
                                    "conflicting_orphan",
                                }:
                                    _wait_for_orphaned_regeneration_updater(
                                        _ACTIVE_REPAIR_INCIDENT_PATH,
                                        orphan,
                                        phase=phase,
                                        phase_attempt=attempt,
                                    )
                                    _clear_regeneration_orphan(
                                        _ACTIVE_REPAIR_INCIDENT_PATH,
                                        orphan,
                                    )
                                    # The updater's return code is unavailable
                                    # after its wrapper died.  Its fresh
                                    # structural nightly summary is the only
                                    # authoritative result, so continue to
                                    # ordinary summary verification below.
                                    return 0, None
                            if _waterlily_scheduler_lock_is_held():
                                # There is an updater in the tiny unidentifiable
                                # Popen->pointer window.  Preserve the repair
                                # lease until its inherited flock releases.
                                _wait_for_scheduler_lock_release(
                                    phase=phase,
                                    phase_attempt=attempt,
                                )
                                return 0, None
                            break
                        if (
                            child_leased
                            and not child_persisted
                            and _ACTIVE_REPAIR_INCIDENT_PATH is not None
                        ):
                            # A nonblocking incident-state lock can be held
                            # momentarily.  Retry persistence while this
                            # worker is alive rather than leaving the watchdog
                            # blind if this process later crashes.
                            child_persisted = _set_repair_regeneration_child(
                                _ACTIVE_REPAIR_INCIDENT_PATH,
                                pid=child_pid,
                                phase=phase,
                                phase_attempt=attempt,
                            )
                        _heartbeat_active_repair_worker(phase=phase, phase_attempt=attempt)
                        time.sleep(_repair_worker_heartbeat_interval())
                    return int(returncode), None
                finally:
                    if child_leased and _ACTIVE_REPAIR_INCIDENT_PATH is not None:
                        _clear_repair_regeneration_child(
                            _ACTIVE_REPAIR_INCIDENT_PATH,
                            phase=phase,
                            phase_attempt=attempt,
                        )
        except Exception as exc:
            return None, type(exc).__name__

    if recovery_args:
        returncode, error_type = run_child(recovery_args, phase="baseline_refresh")
        if error_type:
            return {
                "kind": "regeneration",
                "error_type": error_type,
                "recovery_preflight": recovery_preflight,
                "verification_reason": "baseline_refresh_exception",
            }
        if returncode != 0:
            outcome = {
                "kind": "regeneration",
                "returncode": int(returncode),
                "recovery_preflight": recovery_preflight,
                "verification_reason": "baseline_refresh_nonzero_exit",
            }
            handoff = _safe_nightly_failure_handoff(
                summary_path,
                previous_mtime_ns=previous_mtime_ns,
            )
            if handoff:
                outcome["nightly_failure"] = handoff
            return outcome

    # Recovery after a provider/UI incident must re-fetch the entire current
    # month. The normal rolling incremental window can otherwise verify a
    # fresh cache while retaining the very older rows that a broken UI/parser
    # omitted (the July incident class this repair path exists to prevent).
    returncode, error_type = run_child(("--full",), phase="regeneration")
    if error_type:
        outcome = {
            "kind": "regeneration",
            "error_type": error_type,
            "verification_reason": "runner_exception",
        }
        if recovery_preflight:
            outcome["recovery_preflight"] = recovery_preflight
        return outcome
    if returncode != 0:
        outcome = {
            "kind": "regeneration",
            "returncode": int(returncode),
            "verification_reason": "runner_nonzero_exit",
        }
        if recovery_preflight:
            outcome["recovery_preflight"] = recovery_preflight
        handoff = _safe_nightly_failure_handoff(
            summary_path,
            previous_mtime_ns=previous_mtime_ns,
        )
        if handoff:
            outcome["nightly_failure"] = handoff
        return outcome
    outcome = _verify_waterlily_summary(
        summary_path,
        incident=incident,
        attempt_started_at=attempt_started_at,
        previous_mtime_ns=previous_mtime_ns,
        require_full=True,
    )
    outcome["returncode"] = 0
    if recovery_preflight:
        outcome["recovery_preflight"] = recovery_preflight
    return outcome


def _existing_verified_waterlily_recovery(incident: dict[str, Any]) -> dict[str, Any] | None:
    """Accept a report already regenerated after this incident was captured.

    This closes the loop when an operator or another safe retry completed the
    transactional Waterlily run while the autonomous repair worker was waiting
    on a provider or the scheduler lock.  A stale prior-night summary cannot
    satisfy the incident timestamp requirement.
    """
    reference = _parse_iso(incident.get("repair_started_at")) or _parse_iso(incident.get("created_at"))
    if reference is None:
        return None
    outcome = _verify_waterlily_summary(
        VESSENCE_DATA_HOME / WATERLILY_NIGHTLY_SUMMARY,
        incident=incident,
        attempt_started_at=reference,
        previous_mtime_ns=None,
        require_full=True,
    )
    return outcome if outcome.get("verification_reason") == "verified" else None


def _waterlily_nightly_freshness_grace_seconds() -> int:
    """Return a bounded observation grace, never a report execution timeout."""
    return _positive_int_env("JANE_WATERLILY_NIGHTLY_FRESHNESS_GRACE_SEC", 2 * 60 * 60)


def _waterlily_scheduler_lock_is_held() -> bool:
    """Check the scheduler's flock without waiting or disturbing its owner."""
    try:
        fd = os.open(WATERLILY_NIGHTLY_LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        # An uninspectable lock is treated as active.  The sentinel must not
        # manufacture a duplicate repair while the scheduler state is unknown.
        return True
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            return True
        return False
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _current_waterlily_nightly_period(now: dt.datetime) -> tuple[int, int, dt.datetime]:
    local_now = now.astimezone(WATERLILY_NIGHTLY_TZ)
    scheduled_local = local_now.replace(
        hour=WATERLILY_NIGHTLY_SCHEDULE_HOUR,
        minute=WATERLILY_NIGHTLY_SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )
    return local_now.year, local_now.month, scheduled_local.astimezone(dt.timezone.utc)


def _waterlily_summary_freshness_reason(
    summary_path: Path,
    *,
    year: int,
    month: int,
    scheduled_at: dt.datetime,
) -> str:
    """Return a fixed safe reason when the expected nightly output is absent."""
    try:
        data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "summary_missing"
    except Exception:
        return "summary_unreadable"
    if not isinstance(data, dict):
        return "summary_invalid"
    if data.get("status") != "ok":
        return "summary_not_ok"
    if bool(data.get("dry_run")):
        return "summary_dry_run"
    if data.get("year") != year or data.get("month") != month:
        return "summary_wrong_period"
    started_at = _parse_iso(data.get("started_at"))
    if started_at is None or started_at < scheduled_at:
        return "summary_stale"
    _evidence, reason = _verify_waterlily_report_rebuild_evidence(
        data,
        summary_started_at=started_at,
    )
    return "verified" if reason == "verified" else reason


def _has_active_current_period_waterlily_incident(year: int, month: int) -> bool:
    for path in _resumable_critical_incident_paths():
        try:
            incident = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(incident, dict):
            continue
        incident_year, incident_month = _expected_period(incident)
        if incident_year == year and incident_month == month:
            return True
    return False


def _capture_waterlily_nightly_freshness_failure(
    *,
    year: int,
    month: int,
    reason: str,
) -> dict[str, Any] | None:
    """Capture a fixed sentinel event through the ordinary durable pipeline."""
    from agent_skills.self_healing import capture_report

    return capture_report(
        source=WATERLILY_NIGHTLY_SOURCE,
        category="nightly_freshness_sentinel",
        message="Waterlily nightly report freshness sentinel detected missing verified output",
        payload={
            "auto_repair_priority": "critical",
            "year": int(year),
            "month": int(month),
            "sentinel_reason": str(reason),
        },
        project_root=_waterlily_project_root(),
        tags=["waterlily", "nightly", "freshness-sentinel", "critical-auto-repair"],
        # The watchdog below launches it exactly once under the normal
        # per-incident lease rather than racing capture's detached launcher.
        auto_repair=False,
    )


def _capture_waterlily_ordinary_orphan_failure(
    *,
    year: int,
    month: int,
) -> dict[str, Any] | None:
    """Create one critical coordinator for a proven ordinary orphan updater."""
    from agent_skills.self_healing import capture_report

    return capture_report(
        source=WATERLILY_NIGHTLY_SOURCE,
        category="nightly_orphaned_regeneration",
        message="Waterlily nightly watchdog detected a dead scheduler wrapper with a live updater",
        payload={
            "auto_repair_priority": "critical",
            "year": int(year),
            "month": int(month),
            "sentinel_reason": "ordinary_orphaned_regeneration",
        },
        project_root=_waterlily_project_root(),
        tags=["waterlily", "nightly", "orphaned-regeneration", "critical-auto-repair"],
        # ``resume_critical_repairs`` attaches the exact updater and performs
        # the second stale observation; do not race it from capture itself.
        auto_repair=False,
    )


def _current_period_critical_incident_path(year: int, month: int) -> Path | None:
    """Return the existing period coordinator before creating another one."""
    for path in _resumable_critical_incident_paths():
        try:
            incident = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(incident, dict) and _expected_period(incident) == (year, month):
            return _canonical_current_period_incident_path(path, incident)
    return None


def _observe_ordinary_waterlily_orphan(
    *,
    year: int,
    month: int,
) -> bool:
    """Attach and observe a normal-cron orphan without a report timeout.

    The first unchanged stale marker is merely persisted as a candidate.  The
    existing orphan watchdog requires a second identical stale observation and
    final PID/start-tick/PGID revalidation before sending one SIGTERM to the
    updater's isolated group.
    """
    candidate = _ordinary_waterlily_orphan_candidate()
    if candidate is None:
        return False
    incident_path = _current_period_critical_incident_path(year, month)
    if incident_path is None:
        try:
            incident_path = _incident_path_from_capture(
                _capture_waterlily_ordinary_orphan_failure(year=year, month=month)
            )
        except Exception:
            return False
    if incident_path is None or not _attach_ordinary_waterlily_orphan(incident_path, candidate):
        return False
    _observe_stalled_orphaned_regeneration(incident_path, candidate)
    return True


def ensure_waterlily_nightly_freshness_repair() -> bool:
    """Create a critical repair if a due nightly run left no verified report.

    This is intentionally an *observation* watchdog, not a timeout: it never
    terminates a running report.  A held scheduler lock means the report is
    still legitimately running, so the five-minute watchdog simply checks
    again later.
    """
    if not env_flag_enabled(os.environ, "JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "1"):
        return False
    now = _now()
    year, month, scheduled_at = _current_waterlily_nightly_period(now)
    # This runs even while the inherited scheduler flock is held: a dead
    # wrapper plus a live exact updater is the exceptional case that the old
    # lock-only sentinel could never repair.  It is still not an elapsed-time
    # timeout; only the nonce-bound progress watchdog may later terminate it.
    if _observe_ordinary_waterlily_orphan(year=year, month=month):
        return True
    if now < scheduled_at + dt.timedelta(seconds=_waterlily_nightly_freshness_grace_seconds()):
        return False
    if _waterlily_scheduler_lock_is_held():
        return False
    if _has_active_current_period_waterlily_incident(year, month):
        return False
    reason = _waterlily_summary_freshness_reason(
        VESSENCE_DATA_HOME / WATERLILY_NIGHTLY_SUMMARY,
        year=year,
        month=month,
        scheduled_at=scheduled_at,
    )
    if reason == "verified":
        return False
    try:
        return _capture_waterlily_nightly_freshness_failure(
            year=year,
            month=month,
            reason=reason,
        ) is not None
    except Exception:
        # A capture backend failure is handled by the ordinary deferred spool
        # when possible; another watchdog cycle will observe the same gap.
        return False


def _resumable_critical_incident_paths() -> list[Path]:
    """Find durable Waterlily retries after a runner/process restart."""
    # ``capture_report`` persists a critical incident as ``captured`` before
    # attempting its detached launch.  If Popen fails (host pressure, reboot,
    # or a transient OS error), that status is the only durable evidence.  The
    # five-minute watchdog must resume it just like an in-progress retry.
    statuses = {"captured", "repair_started", "repair_attempting", "repair_retrying", "repair_failed"}
    paths: list[Path] = []
    if not INCIDENT_DIR.is_dir():
        return paths
    for path in sorted(INCIDENT_DIR.glob("*.json")):
        try:
            incident = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(incident, dict) or str(incident.get("status") or "") not in statuses:
                continue
            project_root = _allowed_project_root(str(incident.get("project_root") or VESSENCE_HOME))
        except (OSError, ValueError, SystemExit):
            continue
        if _critical_waterlily_nightly_incident(incident, project_root):
            paths.append(path)
    return paths


def _canonical_current_period_incident_path(
    incident_path: Path,
    incident: dict[str, Any],
    *,
    ignore_held_path: Path | None = None,
) -> Path:
    """Select one durable coordinator for a Waterlily report period.

    A single nightly run can surface distinct structural fingerprints (for
    example a wrapper collision and a source-contract failure).  Preserve all
    evidence files, but let only one unresolved incident coordinate provider
    edits and regeneration for that year/month.  A held legacy incident flock
    wins over timestamp order: it is the only safe evidence of an otherwise
    untracked worker and must be allowed to finish rather than raced.
    """
    expected_year, expected_month = _expected_period(incident)
    if expected_year is None or expected_month is None:
        return incident_path
    candidates: list[tuple[tuple[int, float, str], Path]] = []
    for path in _resumable_critical_incident_paths():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or _expected_period(payload) != (expected_year, expected_month):
            continue
        created = _parse_iso(payload.get("created_at"))
        created_ts = created.timestamp() if created is not None else float("inf")
        # ``0`` sorts a held legacy/current worker before an idle incident.
        # This invokes no signal and records no process command or content.
        held_rank = (
            1
            if ignore_held_path is not None and path == ignore_held_path
            else (0 if _incident_repair_lock_is_held(path) else 1)
        )
        candidates.append(((held_rank, created_ts, path.name), path))
    if not candidates:
        return incident_path
    return min(candidates, key=lambda item: item[0])[1]


def _mark_period_incident_coalesced(
    incident_path: Path,
    canonical_path: Path,
) -> None:
    """Durably mark a queued duplicate without discarding its own evidence."""
    if canonical_path == incident_path:
        return
    _write_incident_update(
        incident_path,
        repair_coalesced_to=canonical_path.name,
        repair_coalesced_at=_iso(),
    )


def resume_critical_repairs() -> int:
    """Launch detached repair workers for persisted critical Waterlily retries.

    The worker's per-incident flock makes this idempotent.  The persisted
    PID/start-tick lease lets the watchdog distinguish a dead/reused worker
    from a still-live one before it launches anything; it never kills a live
    process merely because a report is taking a long time.
    """
    # A request/scheduler capture can fail while the incident backend is
    # degraded.  Replay its private spool before scanning retryable incidents;
    # successful replays create the ordinary durable incident/job flow.
    try:
        from agent_skills.self_healing import drain_deferred_captures

        drain_deferred_captures()
    except Exception:
        # The five-minute watchdog will try again.  Existing critical repairs
        # must still be resumable even if one deferred spool is corrupt.
        pass
    # This closes the failure-before-capture hole (for example a scheduler,
    # host, or wrapper death before the child can write its own incident).
    # It never interrupts a held scheduler lock and only creates a normal
    # durable critical incident when the expected report is overdue.
    ensure_waterlily_nightly_freshness_repair()
    paths = _resumable_critical_incident_paths()
    if not paths:
        return 0
    log_path = LOG_DIR / "self_healing_repair.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
        "JANE_SELF_HEAL_ACTIVE": "1",
    }
    launched = 0
    for path in paths:
        try:
            incident = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(incident, dict):
            continue
        canonical_path = _canonical_current_period_incident_path(path, incident)
        if canonical_path != path:
            _mark_period_incident_coalesced(path, canonical_path)
            continue
        # An old worker can predate its durable PID lease.  Its exact
        # per-incident flock is still a no-replacement condition; mark this
        # state for safe operator visibility but never clear, signal, or
        # launch around it.
        if _incident_repair_lock_is_held(path):
            _write_incident_update(
                path,
                repair_incident_lease_state="held_unidentified",
                repair_incident_lease_observed_at=_iso(),
            )
            continue
        # A legacy active scheduler wrapper can predate the durable child
        # lease in every incident file.  Its exact private pointer still
        # proves a report is live, so make that visible and defer rather than
        # launching another provider/regeneration beside it.  There is no
        # automatic signal on this path: old wrappers may not advertise the
        # newer updater checkpoint capability needed for a safe stall action.
        active_pointer = _active_waterlily_run_pointer_liveness()
        if active_pointer is not None and not _incident_owns_active_waterlily_pointer(
            incident,
            active_pointer,
        ):
            _write_incident_update(
                path,
                repair_active_run_pointer_state="unowned_live",
                repair_active_run_pointer_observed_at=_iso(),
            )
            continue
        # A scheduler wrapper can die after it started its separately
        # sessioned updater.  Check the explicitly adopted updater *before*
        # considering either the old wrapper lease or a replacement repair.
        # This preserves the one active report even when the original repair
        # worker is still alive but has not yet observed its wrapper's exit.
        orphan = _safe_regeneration_orphan(incident.get("repair_regeneration_orphan"))
        if orphan is not None:
            orphan_state = _process_lease_liveness(orphan["updater"])
            if orphan_state == "live":
                _observe_stalled_orphaned_regeneration(path, orphan)
                continue
            if orphan_state == "live_unverified":
                # The strict orphan schema always includes start ticks, but
                # retain this no-replacement guard if a future platform
                # liveness implementation yields an indeterminate state.
                continue
            if orphan_state == "stopped":
                try:
                    os.kill(int(orphan["updater"]["pid"]), signal.SIGCONT)
                except (OSError, TypeError, ValueError):
                    # It can disappear after the liveness check.  The next
                    # pass will clear only the exact persisted handoff.  Do
                    # not launch a replacement while this verified stopped
                    # updater could still be present.
                    continue
                else:
                    _write_incident_update(
                        path,
                        repair_regeneration_orphan_watchdog_action="continued_stopped_updater",
                        repair_regeneration_orphan_watchdog_at=_iso(),
                    )
                    continue
            if orphan_state in {"lost", "reused"}:
                _clear_regeneration_orphan(path, orphan)
                incident["repair_regeneration_orphan"] = None

        # A repair parent can crash while Codex or Claude is still editing in
        # its own session.  That provider is not a report child, but it is
        # equally unsafe to launch a second editor beside it.  Do not signal
        # or resume an unknown/stopped provider here; the exact persisted
        # lease is only a no-replacement guard until it exits.
        provider_state = _repair_provider_child_liveness(incident)
        if provider_state in {"live", "live_unverified", "stopped"}:
            _write_incident_update(
                path,
                repair_provider_child_watchdog_action="continued_provider_child",
                repair_provider_child_watchdog_at=_iso(),
            )
            continue
        if provider_state in {"lost", "reused"}:
            worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else None
            if worker is not None:
                retained_worker = dict(worker)
                retained_worker.pop("provider_child", None)
                _write_incident_update(
                    path,
                    repair_worker=retained_worker,
                    repair_provider_child_lost_at=_iso(),
                    repair_provider_child_lost_reason=provider_state,
                )
                incident["repair_worker"] = retained_worker
        child_state = _repair_regeneration_child_liveness(incident)
        if child_state == "live":
            worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else {}
            child = _safe_regeneration_child_lease(worker.get("regeneration_child"))
            if child is not None:
                _observe_stalled_regeneration_child(path, child)
            # The parent may have crashed, but its child remains the only
            # owner of this regeneration.  Even a malformed progress protocol
            # never authorizes a parallel repair while that verified PID lives.
            continue
        if child_state == "live_unverified":
            # The parent may have crashed, but its no-timeout nightly child is
            # still legitimately rebuilding under the scheduler lock.  Never
            # launch a second repair/regeneration beside it.
            continue
        if child_state == "stopped":
            worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else {}
            child = _safe_regeneration_child_lease(worker.get("regeneration_child"))
            try:
                os.kill(int((child or {}).get("pid") or 0), signal.SIGCONT)
            except (OSError, TypeError, ValueError):
                child_state = "lost"
            else:
                _write_incident_update(
                    path,
                    repair_regeneration_child_watchdog_action="continued_stopped_child",
                    repair_regeneration_child_watchdog_at=_iso(),
                )
                continue
        if child_state in {"lost", "reused"}:
            worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else None
            if worker is not None:
                wrapper = _safe_regeneration_child_lease(worker.get("regeneration_child"))
                if wrapper is not None:
                    adoption, _candidate = _adopt_active_regeneration_orphan(path, wrapper)
                    if adoption in {
                        "adopted",
                        "already_adopted",
                        "live_unpersisted",
                        "conflicting_orphan",
                    }:
                        # The exact pointer proves a live updater.  A state
                        # lock race must never turn that evidence into a
                        # parallel repair; a later watchdog pass will adopt
                        # it or observe the existing orphan.
                        continue
                    # During Popen -> pointer-child attachment there is no
                    # safe updater identity to adopt.  Its inherited scheduler
                    # flock is still a definitive no-replacement condition.
                    if _waterlily_scheduler_lock_is_held():
                        _write_incident_update(
                            path,
                            repair_regeneration_wrapper_lost_while_lock_held_at=_iso(),
                        )
                        continue
                retained_worker = dict(worker)
                retained_worker.pop("regeneration_child", None)
                _write_incident_update(
                    path,
                    repair_worker=retained_worker,
                    repair_regeneration_child_lost_at=_iso(),
                    repair_regeneration_child_lost_reason=child_state,
                )
                incident["repair_worker"] = retained_worker
        worker_state = _repair_worker_liveness(incident)
        if worker_state in {"live", "live_unverified"}:
            continue
        if worker_state == "stopped":
            worker = incident.get("repair_worker") if isinstance(incident.get("repair_worker"), dict) else {}
            try:
                os.kill(int(worker.get("pid") or 0), signal.SIGCONT)
            except (OSError, TypeError, ValueError):
                # The process can disappear between liveness inspection and
                # SIGCONT.  Treat it as lost and let this watchdog launch a
                # fresh worker below.
                worker_state = "lost"
            else:
                _write_incident_update(
                    path,
                    repair_worker_watchdog_action="continued_stopped_worker",
                    repair_worker_watchdog_at=_iso(),
                )
                continue
        if worker_state in {"lost", "reused"}:
            _write_incident_update(
                path,
                repair_worker=None,
                repair_worker_lost_at=_iso(),
                repair_worker_lost_reason=worker_state,
            )
        # A held scheduler flock is always more authoritative than an absent
        # wrapper PID: its owner may be in the small pointer-attachment
        # window, or be a separate currently-running nightly report.  Do not
        # create a second wrapper beside it.
        if _waterlily_scheduler_lock_is_held():
            continue
        try:
            with log_path.open("a", encoding="utf-8") as logf:
                try:
                    log_path.chmod(0o600)
                except OSError:
                    pass
                subprocess.Popen(
                    [PYTHON, str(Path(__file__).resolve()), "--incident", str(path)],
                    cwd=str(VESSENCE_HOME),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            launched += 1
        except Exception:
            # Another watchdog cycle will retry this launch; do not make one
            # damaged incident prevent other persisted critical recoveries.
            continue
    return launched


def _complete_repair(
    prompt: str,
    *,
    timeout: int,
    cwd: str,
    provider_order: tuple[str, ...] = ("codex", "claude"),
    on_provider_started: Callable[[str, int], bool] | None = None,
) -> RepairCompletion:
    """Return private repair output with only safe handoff metadata."""
    from agent_skills.claude_cli_llm import completion_for_critical_repair_result

    result = completion_for_critical_repair_result(
        prompt,
        max_tokens=8192,
        timeout=timeout,
        cwd=cwd,
        provider_order=provider_order,
        on_provider_started=on_provider_started,
    )
    failed_providers = tuple(
        str(attempt.get("provider") or "").strip().lower()
        for attempt in result.failed_attempts
        if isinstance(attempt, dict)
        and str(attempt.get("provider") or "").strip().lower() in _CRITICAL_REPAIR_PROVIDERS
    )
    return RepairCompletion(
        output=result.output,
        provider=result.provider,
        failed_providers=failed_providers,
    )


def _report_header(incident_path: Path, project_root: Path, started: str) -> str:
    return (
        "# Self-Healing Repair Report\n\n"
        f"- Incident: `{incident_path}`\n"
        f"- Project root: `{project_root}`\n"
        f"- Started: `{started}`\n"
    )


def _append_safe_attempt_report(path: Path, outcome: dict[str, Any], *, next_retry_at: str | None = None) -> None:
    safe = _safe_retry_context(outcome)
    lines = ["\n## Repair Attempt", "", "```json", json.dumps(safe, indent=2, sort_keys=True), "```", ""]
    if next_retry_at:
        lines.append(f"- Next retry: `{next_retry_at}`\n")
    _append_private_text(path, "\n".join(lines))


def _retry(
    *,
    incident_path: Path,
    incident: dict[str, Any],
    report_path: Path,
    outcome: dict[str, Any],
    attempt: int,
    provider_cycle: set[str] | None = None,
    next_provider: str | None = None,
    sleep_fn: Callable[[float], None],
) -> None:
    delay = _retry_delay_seconds(attempt)
    next_retry_at = _iso(_now() + dt.timedelta(seconds=delay))
    _update_repair_worker(
        incident_path,
        phase="retry_sleep",
        phase_attempt=attempt,
        progress=True,
    )
    safe_outcome = _safe_retry_context(outcome)
    _write_incident_update(
        incident_path,
        status="repair_retrying",
        repair_attempts=attempt,
        repair_last_attempt_at=_iso(),
        repair_last_outcome=safe_outcome,
        repair_next_retry_at=next_retry_at,
        repair_report_path=str(report_path),
        repair_provider_cycle=sorted(provider_cycle or set()),
        repair_next_provider=(
            next_provider
            if next_provider in _CRITICAL_REPAIR_PROVIDERS
            else "codex"
        ),
    )
    _set_job_status(
        incident,
        "in_progress",
        "Automatic critical repair is retrying until a fresh Waterlily nightly report verifies successfully.",
    )
    _append_safe_attempt_report(report_path, outcome, next_retry_at=next_retry_at)
    sleep_fn(delay)


def run_repair(
    incident_path: Path,
    *,
    completion_fn: Callable[..., str] | None = None,
    regeneration_fn: Callable[[Path, dict[str, Any], int, dt.datetime], dict[str, Any]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_attempts: int | None = None,
) -> str:
    """Repair one incident; critical Waterlily work retries until verified.

    ``max_attempts`` is deliberately an in-process test seam only.  Production
    callers leave it ``None`` so a provider timeout cannot terminally abandon a
    critical nightly recovery.
    """
    global _ACTIVE_REPAIR_INCIDENT_PATH

    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    project_root = _allowed_project_root(str(incident.get("project_root") or VESSENCE_HOME))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started = _iso()
    report_path = REPORT_DIR / f"{started.replace(':', '').replace('-', '')}_{incident.get('id', 'incident')}.md"
    critical_waterlily = _critical_waterlily_nightly_incident(incident, project_root)
    _write_private_text(report_path, _report_header(incident_path, project_root, started))
    _write_incident_update(
        incident_path,
        status="repair_started",
        repair_started_at=started,
        repair_report_path=str(report_path),
        repair_attempts=int(incident.get("repair_attempts") or 0),
    )
    prior_active_incident_path = _ACTIVE_REPAIR_INCIDENT_PATH
    _ACTIVE_REPAIR_INCIDENT_PATH = incident_path
    _update_repair_worker(incident_path, phase="starting", phase_attempt=0, progress=True)

    def finish() -> str:
        # Normal terminal/test-seam exits clear the durable lease.  A crash
        # deliberately leaves it behind so the watchdog can prove the PID is
        # gone and resume the incident without guessing from elapsed time.
        _clear_repair_worker(incident_path)
        global _ACTIVE_REPAIR_INCIDENT_PATH
        if _ACTIVE_REPAIR_INCIDENT_PATH == incident_path:
            _ACTIVE_REPAIR_INCIDENT_PATH = prior_active_incident_path
        return str(report_path)

    if critical_waterlily:
        _set_job_status(
            incident,
            "in_progress",
            "Automatic critical repair is in progress; completion requires a verified fresh Waterlily nightly report.",
        )

    uses_default_completion = completion_fn is None
    completion_fn = completion_fn or _complete_repair
    regeneration_fn = regeneration_fn or _run_waterlily_regeneration
    previous_outcome: dict[str, Any] | None = None
    attempt = int(incident.get("repair_attempts") or 0)
    provider_cycle, next_provider = _provider_cycle_state(incident)
    if critical_waterlily:
        recovered = _existing_verified_waterlily_recovery(incident)
        if recovered is not None:
            recovered["attempt"] = attempt
            _append_safe_attempt_report(report_path, recovered)
            _append_private_text(report_path, "\n- Status: `repair_finished` (fresh regeneration already verified)\n")
            _write_incident_update(
                incident_path,
                status="repair_finished",
                repair_finished_at=_iso(),
                repair_attempts=attempt,
                repair_last_outcome=_safe_retry_context(recovered),
                repair_report_path=str(report_path),
                repair_output_chars=0,
            )
            _set_job_status(
                incident,
                "completed",
                "Automatic repair completed after a fresh Waterlily nightly report was verified.",
            )
            return finish()
    while True:
        attempt += 1
        attempt_started_at = _now()
        _write_incident_update(
            incident_path,
            status="repair_attempting",
            repair_attempts=attempt,
            repair_attempt_started_at=_iso(attempt_started_at),
            repair_report_path=str(report_path),
        )
        _update_repair_worker(
            incident_path,
            phase="provider",
            phase_attempt=attempt,
            progress=True,
        )
        prompt = _build_prompt(
            incident,
            incident_path,
            project_root,
            retry_context=previous_outcome,
        )
        provider_order = _provider_order_for_attempt(provider_cycle, next_provider) if critical_waterlily else ()
        completion_error: Exception | None = None
        output = ""
        provider = ""
        failed_providers: tuple[str, ...] = ()
        outcome: dict[str, Any] | None = None
        project_lease_busy = False
        project_lease = (
            _waterlily_project_repair_lease()
            if critical_waterlily
            else contextlib.nullcontext(True)
        )

        # The project lease covers the only phases that can change Waterlily
        # code or report state: a live provider and its regeneration.  It is
        # deliberately released before retry bookkeeping/backoff, so one
        # unreachable provider cannot monopolize recovery forever.
        with project_lease as project_acquired:
            if not project_acquired:
                project_lease_busy = True
                _write_incident_update(
                    incident_path,
                    repair_project_lease_state="waiting",
                    repair_project_lease_waiting_at=_iso(),
                )
            else:
                if critical_waterlily:
                    _write_incident_update(
                        incident_path,
                        repair_project_lease_state="active",
                        repair_project_lease_acquired_at=_iso(),
                    )

                def persist_provider_child(provider_name: str, provider_pid: int) -> bool:
                    """Accept a provider only after its exact lease is durable."""
                    if _ACTIVE_REPAIR_INCIDENT_PATH != incident_path:
                        return False
                    return _set_repair_provider_child(
                        incident_path,
                        provider=provider_name,
                        pid=provider_pid,
                        phase="provider",
                        phase_attempt=attempt,
                    )

                try:
                    if critical_waterlily and uses_default_completion:
                        completion_result = completion_fn(
                            prompt,
                            timeout=_repair_attempt_timeout(),
                            cwd=str(project_root),
                            provider_order=provider_order,
                            on_provider_started=persist_provider_child,
                        )
                    else:
                        completion_result = completion_fn(
                            prompt,
                            timeout=_repair_attempt_timeout(),
                            cwd=str(project_root),
                        )
                    if isinstance(completion_result, RepairCompletion):
                        output = completion_result.output
                        provider = (
                            completion_result.provider
                            if completion_result.provider in _CRITICAL_REPAIR_PROVIDERS
                            else provider_order[0]
                        )
                        failed_providers = completion_result.failed_providers
                    else:
                        output = completion_result
                        # Test/injected completion seams retain their existing
                        # string API. Production records the actual provider
                        # even after an in-call Codex -> Claude handoff.
                        provider = provider_order[0] if provider_order else ""
                        failed_providers = ()
                except Exception as exc:
                    completion_error = exc
                finally:
                    # Completion returns only after every provider it started
                    # has exited or been reaped. Clear the durable lease before
                    # this worker can retry or hand off.
                    if critical_waterlily and uses_default_completion:
                        _clear_repair_provider_child(
                            incident_path,
                            phase="provider_finished",
                            phase_attempt=attempt,
                        )

                if completion_error is None and critical_waterlily:
                    _update_repair_worker(
                        incident_path,
                        phase="regeneration",
                        phase_attempt=attempt,
                        progress=True,
                    )
                    try:
                        outcome = dict(
                            regeneration_fn(project_root, incident, attempt, attempt_started_at) or {}
                        )
                    except Exception as exc:
                        outcome = {
                            "kind": "regeneration",
                            "error_type": type(exc).__name__,
                            "verification_reason": "regeneration_exception",
                        }

        if project_lease_busy:
            outcome = {
                "attempt": attempt,
                "kind": "coordination",
                "verification_reason": "project_repair_lease_busy",
            }
            previous_outcome = outcome
            _retry(
                incident_path=incident_path,
                incident=incident,
                report_path=report_path,
                outcome=outcome,
                attempt=attempt,
                provider_cycle=provider_cycle,
                next_provider=next_provider,
                sleep_fn=sleep_fn,
            )
            if max_attempts is not None and attempt >= max_attempts:
                return finish()
            continue

        if completion_error is not None:
            exc = completion_error
            outcome = {"attempt": attempt, "kind": "llm", "error_type": type(exc).__name__}
            if critical_waterlily:
                if _is_repair_providers_exhausted(exc):
                    provider_failures = tuple(
                        str(item.get("provider") or "").strip().lower()
                        for item in getattr(exc, "attempts", ())
                        if isinstance(item, dict)
                    )
                else:
                    # An injected/raw completion error has no provider
                    # metadata. It occurred at the selected handoff point.
                    provider_failures = provider_order[:1]
                provider_cycle, next_provider, providers_exhausted = _advance_provider_cycle(
                    provider_cycle,
                    provider_failures,
                )
                outcome.update({
                    "provider_cycle": sorted(provider_cycle),
                    "next_provider": next_provider,
                })
                if providers_exhausted:
                    _notify_repair_provider_exhaustion(
                        incident_path,
                        incident,
                        critical_waterlily=True,
                    )
            if not critical_waterlily:
                # A non-nightly UI incident can use the same deliberate
                # Codex -> Claude completion path.  It does not retry a
                # report forever, but Chieh still needs a durable Vessence
                # alert when both providers have exhausted their repair
                # attempts rather than a silent ``repair_failed`` state.
                if _is_repair_providers_exhausted(exc):
                    _notify_repair_provider_exhaustion(
                        incident_path,
                        incident,
                        critical_waterlily=False,
                    )
                _append_private_text(report_path, f"\n## Runner Failure\n\n{type(exc).__name__}\n")
                _write_incident_update(
                    incident_path,
                    status="repair_failed",
                    repair_finished_at=_iso(),
                    repair_report_path=str(report_path),
                    repair_last_outcome=_safe_retry_context(outcome),
                )
                return finish()
            previous_outcome = outcome
            _retry(
                incident_path=incident_path,
                incident=incident,
                report_path=report_path,
                outcome=outcome,
                attempt=attempt,
                provider_cycle=provider_cycle,
                next_provider=next_provider,
                sleep_fn=sleep_fn,
            )
            if max_attempts is not None and attempt >= max_attempts:
                return finish()
            continue

        if not critical_waterlily:
            # Existing non-critical behavior remains available.  The output is
            # private, while incident JSON receives no untrusted excerpt.
            _append_private_text(report_path, f"\n## Runner Output\n\n{output}\n")
            _write_incident_update(
                incident_path,
                status="repair_finished",
                repair_finished_at=_iso(),
                repair_report_path=str(report_path),
                repair_output_chars=len(output),
            )
            _set_job_status(incident, "completed", "Automatic repair runner completed.")
            return finish()

        outcome = outcome or {
            "kind": "regeneration",
            "verification_reason": "regeneration_unavailable",
        }
        outcome["attempt"] = attempt
        if provider in _CRITICAL_REPAIR_PROVIDERS:
            outcome["provider"] = provider
        if outcome.get("verification_reason") == "verified":
            _append_safe_attempt_report(report_path, outcome)
            _append_private_text(report_path, "\n- Status: `repair_finished` (fresh regeneration verified)\n")
            _write_incident_update(
                incident_path,
                status="repair_finished",
                repair_finished_at=_iso(),
                repair_attempts=attempt,
                repair_last_outcome=_safe_retry_context(outcome),
                repair_report_path=str(report_path),
                repair_output_chars=len(output),
            )
            _set_job_status(
                incident,
                "completed",
                "Automatic repair completed after a fresh Waterlily nightly report was verified.",
            )
            return finish()

        provider_cycle, next_provider, providers_exhausted = _advance_provider_cycle(
            provider_cycle,
            tuple(failed_providers) + ((provider,) if provider else ()),
        )
        outcome.update({
            "provider_cycle": sorted(provider_cycle),
            "next_provider": next_provider,
        })
        if providers_exhausted:
            _notify_repair_provider_exhaustion(
                incident_path,
                incident,
                critical_waterlily=True,
            )
        previous_outcome = outcome
        _retry(
            incident_path=incident_path,
            incident=incident,
            report_path=report_path,
            outcome=outcome,
            attempt=attempt,
            provider_cycle=provider_cycle,
            next_provider=next_provider,
            sleep_fn=sleep_fn,
        )
        if max_attempts is not None and attempt >= max_attempts:
            return finish()


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--incident")
    group.add_argument("--resume-critical", action="store_true")
    args = parser.parse_args()
    if args.resume_critical:
        print(f"self-healing critical repair resumes launched: {resume_critical_repairs()}")
        return
    incident_path = Path(args.incident).expanduser().resolve()
    with _incident_repair_lock(incident_path) as acquired:
        if not acquired:
            print("self-healing repair already running for this incident")
            return
        try:
            incident = json.loads(incident_path.read_text(encoding="utf-8"))
            project_root = _allowed_project_root(str(incident.get("project_root") or VESSENCE_HOME))
            critical_waterlily = isinstance(incident, dict) and _critical_waterlily_nightly_incident(
                incident,
                project_root,
            )
        except Exception:
            # ``run_repair`` remains the authoritative error/report path for
            # malformed/non-Waterlily incidents.
            incident = {}
            critical_waterlily = False
        if critical_waterlily:
            canonical_path = _canonical_current_period_incident_path(
                incident_path,
                incident,
                ignore_held_path=incident_path,
            )
            if canonical_path != incident_path:
                _mark_period_incident_coalesced(incident_path, canonical_path)
                print("self-healing Waterlily incident coalesced to the current-period coordinator")
                return
            active_pointer = _active_waterlily_run_pointer_liveness()
            if active_pointer is not None and not _incident_owns_active_waterlily_pointer(
                incident,
                active_pointer,
            ):
                _write_incident_update(
                    incident_path,
                    repair_active_run_pointer_state="unowned_live",
                    repair_active_run_pointer_observed_at=_iso(),
                )
                print("self-healing Waterlily repair deferred while an unowned active report is live")
                return
        # ``run_repair`` takes the project flock only around an active
        # provider/regeneration operation.  Do not hold it across the durable
        # retry loop here: that would make a sleeping duplicate worker block
        # every later Waterlily recovery indefinitely.
        report_path = run_repair(incident_path)
    print(f"self-healing repair report: {report_path}")


if __name__ == "__main__":
    main()
