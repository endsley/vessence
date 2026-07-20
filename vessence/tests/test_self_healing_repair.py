import datetime as dt
import contextlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from agent_skills.claude_cli_llm import RepairProvidersExhausted
from agent_skills import self_healing_repair as repair


def _configure_paths(monkeypatch, tmp_path):
    vessence_home = tmp_path / "vessence"
    data_home = tmp_path / "data"
    waterlily_root = tmp_path / "waterlily"
    queue = vessence_home / "configs" / "job_queue"
    queue.mkdir(parents=True)
    waterlily_root.mkdir()
    monkeypatch.setattr(repair, "VESSENCE_HOME", vessence_home)
    monkeypatch.setattr(repair, "VESSENCE_DATA_HOME", data_home)
    monkeypatch.setattr(repair, "LOG_DIR", data_home / "logs")
    monkeypatch.setattr(repair, "SELF_HEAL_DIR", data_home / "self_healing")
    monkeypatch.setattr(repair, "INCIDENT_DIR", data_home / "self_healing" / "incidents")
    monkeypatch.setattr(repair, "REPORT_DIR", data_home / "self_healing" / "reports")
    # Resume tests must not depend on a real Waterlily scheduler process that
    # happens to be holding the production flock while this isolated fixture
    # proves its own durable incident behavior.
    monkeypatch.setattr(repair, "WATERLILY_NIGHTLY_LOCK", tmp_path / "nightly.lock")
    monkeypatch.setenv("JANE_WATERLILY_PROJECT_ROOT", str(waterlily_root))
    # Individual freshness-sentinel tests opt in.  Other repair tests should
    # not create a second incident merely because their isolated fixture has
    # no nightly summary.
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "0")
    return vessence_home, data_home, waterlily_root, queue


def _critical_incident(tmp_path, waterlily_root, queue):
    job_path = queue / "job_1_self_heal.md"
    job_path.write_text(
        "# Job: self heal\nStatus: pending\nPriority: high\n",
        encoding="utf-8",
    )
    incident = {
        "id": "safe-incident",
        "source": "waterlily_nightly_reports",
        "project_root": str(waterlily_root),
        "tags": ["waterlily", "critical-auto-repair"],
        "payload": {"auto_repair_priority": "critical", "year": 2026, "month": 7},
        "job_path": str(job_path),
    }
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(incident), encoding="utf-8")
    return path, job_path


def _verified_nightly_summary(*, mode="incremental", practitioners=None):
    """Return a PHI-free structural success summary from the nightly runner."""
    practitioners = practitioners or ["Test Practitioner One", "Test Practitioner Two"]
    income_type = "income" if mode == "incremental" else "income_full"
    error_type = "error_check" if mode == "incremental" else "error_check_full"
    rebuild_type = "cache_rebuild" if mode == "incremental" else "full_current_month_refresh"
    generated_at = "2026-07-18T12:00:01Z"
    results = [
        {"type": error_type, "generated_at": generated_at},
        *(
            {"type": income_type, "generated_at": generated_at}
            for _ in practitioners
        ),
        {"type": "total_income", "generated_at": generated_at},
        {"type": "fsb_bank_error_check", "status": "skipped"},
    ]
    return {
        "status": "ok",
        "dry_run": False,
        "mode": mode,
        "year": 2026,
        "month": 7,
        "started_at": "2026-07-18T12:00:00Z",
        "practitioners": practitioners,
        "steps": [
            {"type": "acubliss_ui_canary"},
            {"type": "acubliss_patient_notes_ui_canary"},
            {"type": "acubliss_package_detail_ui_canary"},
            {"type": "dasys_ui_canary"},
            {"type": "dasys_payment_ui_canary"},
            {"type": "dasys_files_ui_canary"},
            {"type": rebuild_type, "results": results},
            {"type": "semantic_postflight", "status": "passed"},
        ],
    }


def test_critical_repair_retries_timeout_then_completes_only_after_verified_regeneration(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, job_path = _critical_incident(tmp_path, waterlily_root, queue)
    completion_calls = []
    regeneration_calls = []
    delays = []

    def complete(prompt, **kwargs):
        completion_calls.append(prompt)
        if len(completion_calls) == 1:
            raise subprocess.TimeoutExpired(["codex", "do-not-persist-this"], timeout=3)
        return "LLM response containing do-not-persist-this"

    def regenerate(root, incident, attempt, started_at):
        regeneration_calls.append((root, attempt, started_at))
        return {
            "kind": "regeneration",
            "returncode": 0,
            "summary_status": "ok",
            "summary_year": 2026,
            "summary_month": 7,
            "summary_fresh": True,
            "verification_reason": "verified",
        }

    report_path = Path(
        repair.run_repair(
            incident_path,
            completion_fn=complete,
            regeneration_fn=regenerate,
            sleep_fn=delays.append,
        )
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")
    assert len(completion_calls) == 2
    assert len(regeneration_calls) == 1
    assert delays
    assert stored["status"] == "repair_finished"
    assert stored["repair_attempts"] == 2
    assert stored["repair_worker"] is None
    assert "repair_output_excerpt" not in stored
    assert "do-not-persist-this" not in report
    assert "do-not-persist-this" not in json.dumps(stored)
    assert "Status: completed" in job_path.read_text(encoding="utf-8")


def test_critical_repair_keeps_job_in_progress_after_failed_regeneration_then_retries(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, job_path = _critical_incident(tmp_path, waterlily_root, queue)
    completion_calls = []
    regeneration_calls = []

    def complete(prompt, **kwargs):
        completion_calls.append(prompt)
        if len(completion_calls) == 2:
            assert "Status: in_progress" in job_path.read_text(encoding="utf-8")
        return "finished repair"

    def regenerate(root, incident, attempt, started_at):
        regeneration_calls.append(attempt)
        if attempt == 1:
            return {
                "kind": "regeneration",
                "returncode": 1,
                "verification_reason": "runner_nonzero_exit",
                "untrusted_error": "do-not-persist-this",
            }
        return {
            "kind": "regeneration",
            "returncode": 0,
            "summary_status": "ok",
            "summary_year": 2026,
            "summary_month": 7,
            "summary_fresh": True,
            "verification_reason": "verified",
        }

    report_path = Path(
        repair.run_repair(
            incident_path,
            completion_fn=complete,
            regeneration_fn=regenerate,
            sleep_fn=lambda seconds: None,
        )
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert completion_calls and len(completion_calls) == 2
    assert regeneration_calls == [1, 2]
    assert stored["status"] == "repair_finished"
    assert "Status: completed" in job_path.read_text(encoding="utf-8")
    assert "do-not-persist-this" not in report_path.read_text(encoding="utf-8")
    assert "do-not-persist-this" not in json.dumps(stored)


def test_critical_repair_rotates_to_claude_after_unverified_codex_regeneration(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    provider_orders = []

    def complete(_prompt, *, provider_order, **_kwargs):
        provider_orders.append(tuple(provider_order))
        provider = "codex" if len(provider_orders) == 1 else "claude"
        return repair.RepairCompletion(output="private output", provider=provider)

    def regenerate(_root, _incident, attempt, _started_at):
        return {
            "kind": "regeneration",
            "summary_fresh": attempt == 2,
            "verification_reason": "verified" if attempt == 2 else "runner_nonzero_exit",
        }

    monkeypatch.setattr(repair, "_complete_repair", complete)
    repair.run_repair(
        incident_path,
        regeneration_fn=regenerate,
        sleep_fn=lambda _seconds: None,
    )

    assert provider_orders == [("codex", "claude"), ("claude",)]
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["status"] == "repair_finished"
    assert stored["repair_last_outcome"]["provider"] == "claude"


def test_critical_repair_restart_honors_persisted_claude_handoff(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    incident.update({"repair_provider_cycle": ["codex"], "repair_next_provider": "claude"})
    incident_path.write_text(json.dumps(incident), encoding="utf-8")
    provider_orders = []

    def complete(_prompt, *, provider_order, **_kwargs):
        provider_orders.append(tuple(provider_order))
        return repair.RepairCompletion(output="private output", provider="claude")

    monkeypatch.setattr(repair, "_complete_repair", complete)
    repair.run_repair(
        incident_path,
        regeneration_fn=lambda *_args: {"kind": "regeneration", "summary_fresh": True, "verification_reason": "verified"},
        sleep_fn=lambda _seconds: None,
    )

    assert provider_orders == [("claude",)]


def test_two_unverified_provider_outputs_notify_once_then_reset_durable_cycle(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    provider_orders = []
    announcements = []

    def complete(_prompt, *, provider_order, **_kwargs):
        provider_orders.append(tuple(provider_order))
        provider = "codex" if len(provider_orders) == 1 else "claude"
        return repair.RepairCompletion(output="private output", provider=provider)

    monkeypatch.setattr(repair, "_complete_repair", complete)
    monkeypatch.setattr(
        repair,
        "_append_repair_failure_announcement",
        lambda *_args: announcements.append(True),
    )
    repair.run_repair(
        incident_path,
        regeneration_fn=lambda *_args: {"kind": "regeneration", "verification_reason": "runner_nonzero_exit"},
        sleep_fn=lambda _seconds: None,
        max_attempts=2,
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert provider_orders == [("codex", "claude"), ("claude",)]
    assert announcements == [True]
    assert stored["repair_provider_cycle"] == []
    assert stored["repair_next_provider"] == "codex"


def test_verify_waterlily_summary_requires_fresh_successful_expected_period(tmp_path):
    summary = tmp_path / "latest.json"
    started = dt.datetime(2026, 7, 18, 12, 0, 0, 500000, tzinfo=dt.timezone.utc)
    summary.write_text(json.dumps(_verified_nightly_summary()), encoding="utf-8")
    incident = {"payload": {"year": 2026, "month": 7}}

    verified = repair._verify_waterlily_summary(
        summary,
        incident=incident,
        attempt_started_at=started,
        previous_mtime_ns=None,
    )

    assert verified["verification_reason"] == "verified"
    assert verified["summary_fresh"] is True
    assert verified["expected_income_reports"] == 2
    assert verified["verified_income_reports"] == 2


@pytest.mark.parametrize("mode", ["incremental", "full"])
def test_verify_waterlily_summary_requires_complete_current_period_report_evidence(tmp_path, mode):
    summary = tmp_path / "latest.json"
    started = dt.datetime(2026, 7, 18, 12, 0, 0, tzinfo=dt.timezone.utc)
    summary.write_text(json.dumps(_verified_nightly_summary(mode=mode)), encoding="utf-8")

    result = repair._verify_waterlily_summary(
        summary,
        incident={"payload": {"year": 2026, "month": 7}},
        attempt_started_at=started,
        previous_mtime_ns=None,
    )

    assert result["verification_reason"] == "verified"
    assert result["summary_mode"] == mode


def test_repair_verification_rejects_incremental_summary_when_full_recovery_is_required(tmp_path):
    summary = tmp_path / "latest.json"
    summary.write_text(json.dumps(_verified_nightly_summary(mode="incremental")), encoding="utf-8")

    result = repair._verify_waterlily_summary(
        summary,
        incident={"payload": {"year": 2026, "month": 7}},
        attempt_started_at=dt.datetime(2026, 7, 18, 12, 0, 0, tzinfo=dt.timezone.utc),
        previous_mtime_ns=None,
        require_full=True,
    )

    assert result["summary_fresh"] is False
    assert result["verification_reason"] == "summary_recovery_not_full"


def test_verify_waterlily_summary_rejects_ok_summary_without_every_income_report(tmp_path):
    summary = tmp_path / "latest.json"
    payload = _verified_nightly_summary()
    rebuild = next(step for step in payload["steps"] if step["type"] == "cache_rebuild")
    rebuild["results"] = [
        result for result in rebuild["results"] if result.get("type") != "income"
    ]
    summary.write_text(json.dumps(payload), encoding="utf-8")

    result = repair._verify_waterlily_summary(
        summary,
        incident={"payload": {"year": 2026, "month": 7}},
        attempt_started_at=dt.datetime(2026, 7, 18, 12, 0, 0, tzinfo=dt.timezone.utc),
        previous_mtime_ns=None,
    )

    assert result["summary_fresh"] is False
    assert result["verification_reason"] == "summary_income_report_count_mismatch"


def test_nightly_freshness_sentinel_captures_missing_due_report(monkeypatch, tmp_path):
    _vessence_home, _data_home, _waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "1")
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_GRACE_SEC", "1")
    monkeypatch.setattr(repair, "_now", lambda: dt.datetime(2026, 7, 18, 6, 0, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: False)
    monkeypatch.setattr(repair, "_has_active_current_period_waterlily_incident", lambda *_args: False)
    captured = []
    monkeypatch.setattr(
        repair,
        "_capture_waterlily_nightly_freshness_failure",
        lambda **kwargs: captured.append(kwargs) or {"status": "captured"},
    )

    assert repair.ensure_waterlily_nightly_freshness_repair() is True
    assert captured == [{"year": 2026, "month": 7, "reason": "summary_missing"}]


def test_nightly_freshness_sentinel_accepts_complete_fresh_report(monkeypatch, tmp_path):
    _vessence_home, data_home, _waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "1")
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_GRACE_SEC", "1")
    monkeypatch.setattr(repair, "_now", lambda: dt.datetime(2026, 7, 18, 13, 0, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: False)
    monkeypatch.setattr(repair, "_has_active_current_period_waterlily_incident", lambda *_args: False)
    summary = data_home / "logs" / "waterlily_nightly_reports" / "latest.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(json.dumps(_verified_nightly_summary()), encoding="utf-8")
    monkeypatch.setattr(
        repair,
        "_capture_waterlily_nightly_freshness_failure",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("fresh report must not be captured")),
    )

    assert repair.ensure_waterlily_nightly_freshness_repair() is False


def test_nightly_freshness_sentinel_never_captures_while_scheduler_lock_is_held(monkeypatch, tmp_path):
    _vessence_home, _data_home, _waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "1")
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_GRACE_SEC", "1")
    monkeypatch.setattr(repair, "_now", lambda: dt.datetime(2026, 7, 18, 6, 0, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: True)
    monkeypatch.setattr(
        repair,
        "_capture_waterlily_nightly_freshness_failure",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("active scheduler must not be captured")),
    )

    assert repair.ensure_waterlily_nightly_freshness_repair() is False


def test_ordinary_orphan_candidate_requires_dead_wrapper_live_isolated_updater_and_held_lock(monkeypatch):
    wrapper = {"pid": 4241, "start_ticks": "111"}
    updater = {"pid": 4242, "start_ticks": "222"}
    pointer = {"version": 1, "run_nonce": "a" * 32, "wrapper": wrapper, "child": updater}
    candidate = {"version": 1, "wrapper": wrapper, "updater": updater}
    monkeypatch.setattr(repair, "_active_waterlily_run_pointer_liveness", lambda: dict(pointer))
    monkeypatch.setattr(
        repair,
        "_process_lease_liveness",
        lambda lease: "lost" if lease == wrapper else "live" if lease == updater else "none",
    )
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: True)
    monkeypatch.setattr(repair, "_active_regeneration_orphan_candidate", lambda lease: candidate if lease == wrapper else None)
    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda lease: int(lease["pid"]))

    assert repair._ordinary_waterlily_orphan_candidate() == candidate

    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda _lease: None)
    assert repair._ordinary_waterlily_orphan_candidate() is None


def test_freshness_watchdog_adopts_ordinary_orphan_before_lock_only_deferral(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("JANE_WATERLILY_NIGHTLY_FRESHNESS_SENTINEL", "1")
    wrapper = {"pid": 4241, "start_ticks": "111"}
    updater = {"pid": 4242, "start_ticks": "222"}
    candidate = {"version": 1, "wrapper": wrapper, "updater": updater}
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "ordinary-orphan.json"
    incident_path.write_text(
        json.dumps({
            "id": "ordinary-orphan",
            "source": "waterlily_nightly_reports",
            "project_root": str(waterlily_root),
            "status": "captured",
            "tags": ["critical-auto-repair"],
            "payload": {"auto_repair_priority": "critical", "year": 2026, "month": 7},
        }),
        encoding="utf-8",
    )
    observed = []
    monkeypatch.setattr(repair, "_now", lambda: dt.datetime(2026, 7, 18, 6, 0, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(repair, "_ordinary_waterlily_orphan_candidate", lambda: candidate)
    monkeypatch.setattr(repair, "_current_period_critical_incident_path", lambda *_args: incident_path)
    monkeypatch.setattr(
        repair,
        "_observe_stalled_orphaned_regeneration",
        lambda path, orphan: observed.append((path, orphan)) or "candidate",
    )
    monkeypatch.setattr(
        repair,
        "_capture_waterlily_nightly_freshness_failure",
        lambda **_kwargs: pytest.fail("ordinary orphan must not be treated as an ordinary missing report"),
    )

    assert repair.ensure_waterlily_nightly_freshness_repair() is True
    assert repair.ensure_waterlily_nightly_freshness_repair() is True

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_regeneration_orphan"] == candidate
    assert observed == [(incident_path, candidate), (incident_path, candidate)]


def test_critical_retry_releases_project_lease_when_another_operation_is_busy(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)

    @contextlib.contextmanager
    def busy_project_lease():
        yield False

    monkeypatch.setattr(repair, "_waterlily_project_repair_lease", busy_project_lease)
    completion_calls = []
    monkeypatch.setattr(
        repair,
        "_complete_repair",
        lambda *_args, **_kwargs: completion_calls.append(True)
        or (_ for _ in ()).throw(AssertionError("a busy project lease must not start a provider")),
    )

    repair.run_repair(
        incident_path,
        sleep_fn=lambda _seconds: None,
        max_attempts=1,
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert completion_calls == []
    assert stored["repair_project_lease_state"] == "waiting"
    assert "repair_project_lease_waiting_at" in stored
    assert stored["repair_last_outcome"]["verification_reason"] == "project_repair_lease_busy"


def test_critical_retry_releases_project_lease_before_backoff_sleep(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    lease_state = {"active": False, "events": []}

    @contextlib.contextmanager
    def tracked_project_lease():
        assert lease_state["active"] is False
        lease_state["active"] = True
        lease_state["events"].append("entered")
        try:
            yield True
        finally:
            lease_state["active"] = False
            lease_state["events"].append("released")

    monkeypatch.setattr(repair, "_waterlily_project_repair_lease", tracked_project_lease)

    def provider_failure(*_args, **_kwargs):
        assert lease_state["active"] is True
        raise RuntimeError("safe failure")

    def sleep(_seconds):
        assert lease_state["active"] is False
        lease_state["events"].append("slept")

    repair.run_repair(
        incident_path,
        completion_fn=provider_failure,
        sleep_fn=sleep,
        max_attempts=1,
    )

    assert lease_state["events"] == ["entered", "released", "slept"]


def test_critical_project_lease_covers_provider_and_regeneration_together(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    lease_state = {"active": False, "events": []}

    @contextlib.contextmanager
    def tracked_project_lease():
        assert lease_state["active"] is False
        lease_state["active"] = True
        lease_state["events"].append("entered")
        try:
            yield True
        finally:
            lease_state["active"] = False
            lease_state["events"].append("released")

    monkeypatch.setattr(repair, "_waterlily_project_repair_lease", tracked_project_lease)

    def complete(*_args, **_kwargs):
        assert lease_state["active"] is True
        return repair.RepairCompletion(output="private", provider="codex")

    def regenerate(*_args):
        assert lease_state["active"] is True
        return {"kind": "regeneration", "verification_reason": "verified"}

    repair.run_repair(incident_path, completion_fn=complete, regeneration_fn=regenerate)

    assert lease_state["events"] == ["entered", "released"]


def test_critical_provider_lease_is_persisted_then_cleared_after_reap(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    start_ticks, _state = observed
    provider_leases = []

    def complete(_prompt, *, on_provider_started, **_kwargs):
        assert on_provider_started("codex", os.getpid()) is True
        assert repair._heartbeat_active_repair_worker(phase="provider", phase_attempt=1) is True
        stored = json.loads(incident_path.read_text(encoding="utf-8"))
        provider_leases.append(stored["repair_worker"]["provider_child"])
        return repair.RepairCompletion(output="private", provider="codex")

    original_clear = repair._clear_repair_provider_child

    def record_clear(*args, **kwargs):
        changed = original_clear(*args, **kwargs)
        stored = json.loads(incident_path.read_text(encoding="utf-8"))
        assert "provider_child" not in stored["repair_worker"]
        return changed

    monkeypatch.setattr(repair, "_complete_repair", complete)
    monkeypatch.setattr(repair, "_clear_repair_provider_child", record_clear)
    repair.run_repair(
        incident_path,
        regeneration_fn=lambda *_args: {"kind": "regeneration", "verification_reason": "verified"},
    )

    assert provider_leases == [{"provider": "codex", "pid": os.getpid(), "start_ticks": start_ticks}]


def test_repair_regeneration_never_reintroduces_legacy_timeout(monkeypatch):
    monkeypatch.setenv("JANE_SELF_HEAL_REGENERATION_ATTEMPT_TIMEOUT_SEC", "1")

    assert repair._regeneration_timeout() is None


def test_resume_critical_repairs_relaunches_only_persisted_critical_waterlily_incidents(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    critical = repair.INCIDENT_DIR / "critical.json"
    critical.write_text(
        json.dumps(
            {
                "id": "critical",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
            }
        ),
        encoding="utf-8",
    )
    (repair.INCIDENT_DIR / "finished.json").write_text(
        json.dumps(
            {
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_finished",
                "tags": ["critical-auto-repair"],
            }
        ),
        encoding="utf-8",
    )
    captured = repair.INCIDENT_DIR / "captured.json"
    captured.write_text(
        json.dumps(
            {
                "id": "captured",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                # This is the durable state left if the initial detached
                # Popen launch fails before the worker can update it.
                "status": "captured",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
            }
        ),
        encoding="utf-8",
    )
    launched = []
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: launched.append((command, kwargs)))

    assert repair.resume_critical_repairs() == 2
    assert {tuple(command[-2:]) for command, _kwargs in launched} == {
        ("--incident", str(critical)),
        ("--incident", str(captured)),
    }
    for _command, kwargs in launched:
        assert kwargs["start_new_session"] is True
        assert kwargs["env"]["JANE_SELF_HEAL_ACTIVE"] == "1"


def test_resume_critical_repairs_does_not_replace_legacy_held_incident_lock(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "legacy-held.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "legacy-held",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                # Deliberately no repair_worker: this models a worker that
                # started before durable PID/start-tick leases existed.
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "_incident_repair_lock_is_held", lambda path: path == incident_path)
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("an unidentified held incident lock must block replacement"),
    )

    assert repair.resume_critical_repairs() == 0
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_incident_lease_state"] == "held_unidentified"
    assert "repair_incident_lease_observed_at" in stored


def test_resume_critical_repairs_observes_unowned_legacy_active_pointer_without_signal(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "legacy-pointer.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "legacy-pointer",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "_incident_repair_lock_is_held", lambda _path: False)
    monkeypatch.setattr(
        repair,
        "_active_waterlily_run_pointer_liveness",
        lambda: {
            "version": 1,
            "run_nonce": "a" * 32,
            "wrapper": {"pid": 4242, "start_ticks": "123"},
            "child": {"pid": 4343, "start_ticks": "456"},
        },
    )
    signals = []
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("an unowned active pointer must block replacement"),
    )

    assert repair.resume_critical_repairs() == 0
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_active_run_pointer_state"] == "unowned_live"
    assert signals == []


def test_resume_critical_repairs_coalesces_distinct_failure_fingerprints_for_one_period(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    canonical = repair.INCIDENT_DIR / "first.json"
    duplicate = repair.INCIDENT_DIR / "second.json"
    for path, created_at, incident_id in (
        (canonical, "2026-07-18T01:00:00+00:00", "first"),
        (duplicate, "2026-07-18T02:00:00+00:00", "second"),
    ):
        path.write_text(
            json.dumps(
                {
                    "id": incident_id,
                    "source": "waterlily_nightly_reports",
                    "project_root": str(waterlily_root),
                    "status": "captured",
                    "created_at": created_at,
                    "tags": ["critical-auto-repair"],
                    "payload": {
                        "auto_repair_priority": "critical",
                        "year": 2026,
                        "month": 7,
                    },
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(repair, "_incident_repair_lock_is_held", lambda _path: False)
    launched = []
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: launched.append((command, kwargs)))

    assert repair.resume_critical_repairs() == 1
    assert [command[-1] for command, _kwargs in launched] == [str(canonical)]
    stored_duplicate = json.loads(duplicate.read_text(encoding="utf-8"))
    assert stored_duplicate["repair_coalesced_to"] == canonical.name


def test_resume_critical_repairs_keeps_distinct_periods_independently_eligible(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    for month in (7, 8):
        (repair.INCIDENT_DIR / f"period-{month}.json").write_text(
            json.dumps(
                {
                    "id": f"period-{month}",
                    "source": "waterlily_nightly_reports",
                    "project_root": str(waterlily_root),
                    "status": "captured",
                    "created_at": f"2026-07-18T0{month - 6}:00:00+00:00",
                    "tags": ["critical-auto-repair"],
                    "payload": {
                        "auto_repair_priority": "critical",
                        "year": 2026,
                        "month": month,
                    },
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(repair, "_incident_repair_lock_is_held", lambda _path: False)
    launched = []
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: launched.append((command, kwargs)))

    assert repair.resume_critical_repairs() == 2
    assert {Path(command[-1]).name for command, _kwargs in launched} == {"period-7.json", "period-8.json"}


def test_main_coalesces_new_same_period_incident_to_existing_coordinator(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    existing = repair.INCIDENT_DIR / "existing.json"
    incoming = repair.INCIDENT_DIR / "incoming.json"
    for path, created_at, incident_id in (
        (existing, "2026-07-18T01:00:00+00:00", "existing"),
        (incoming, "2026-07-18T02:00:00+00:00", "incoming"),
    ):
        path.write_text(
            json.dumps(
                {
                    "id": incident_id,
                    "source": "waterlily_nightly_reports",
                    "project_root": str(waterlily_root),
                    "status": "captured",
                    "created_at": created_at,
                    "tags": ["critical-auto-repair"],
                    "payload": {
                        "auto_repair_priority": "critical",
                        "year": 2026,
                        "month": 7,
                    },
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(
        repair,
        "run_repair",
        lambda *_args, **_kwargs: pytest.fail("a coalesced duplicate must not start its own repair"),
    )
    monkeypatch.setattr(sys, "argv", ["self_healing_repair.py", "--incident", str(incoming)])

    repair.main()

    stored = json.loads(incoming.read_text(encoding="utf-8"))
    assert stored["repair_coalesced_to"] == existing.name


def test_main_defers_unowned_live_active_pointer_before_provider_launch(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "active-pointer.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "active-pointer",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "captured",
                "created_at": "2026-07-18T01:00:00+00:00",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical", "year": 2026, "month": 7},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        repair,
        "_active_waterlily_run_pointer_liveness",
        lambda: {
            "version": 1,
            "run_nonce": "a" * 32,
            "wrapper": {"pid": 4242, "start_ticks": "123"},
            "child": {"pid": 4343, "start_ticks": "456"},
        },
    )
    monkeypatch.setattr(
        repair,
        "run_repair",
        lambda *_args, **_kwargs: pytest.fail("an unowned live report must block a second provider"),
    )
    monkeypatch.setattr(sys, "argv", ["self_healing_repair.py", "--incident", str(incident_path)])

    repair.main()

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_active_run_pointer_state"] == "unowned_live"


def test_repair_worker_liveness_requires_matching_pid_start_ticks():
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    start_ticks, _state = observed

    assert repair._repair_worker_liveness(
        {"repair_worker": {"pid": os.getpid(), "start_ticks": start_ticks}}
    ) == "live"
    assert repair._repair_worker_liveness(
        {"repair_worker": {"pid": os.getpid(), "start_ticks": "0"}}
    ) == "reused"


def test_resume_critical_repairs_does_not_replace_a_live_orphaned_regeneration_child(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    start_ticks, _state = observed
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "orphaned-child.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "orphaned-child",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                # A dead parent is deliberate: the live child is the reason
                # the watchdog must not start a replacement repair yet.
                "repair_worker": {
                    "pid": 999999,
                    "start_ticks": "1",
                    "regeneration_child": {"pid": os.getpid(), "start_ticks": start_ticks},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("watchdog must not overlap a live orphaned regeneration child"),
    )

    assert repair.resume_critical_repairs() == 0


def test_resume_critical_repairs_does_not_overlap_a_live_orphaned_provider(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    start_ticks, _state = observed
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "orphaned-provider.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "orphaned-provider",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                "repair_worker": {
                    "pid": 999999,
                    "start_ticks": "1",
                    "provider_child": {
                        "provider": "codex",
                        "pid": os.getpid(),
                        "start_ticks": start_ticks,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("a live provider child must block a second editor"),
    )

    assert repair.resume_critical_repairs() == 0
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_provider_child_watchdog_action"] == "continued_provider_child"


def _active_pointer_protocol(pointer, *, marker=None, stalled=False):
    """Return a PHI-free fake of the allowlisted nightly progress protocol."""
    marker = marker or {
        "version": 1,
        "run_nonce": str(pointer["run_nonce"]),
        "seq": 2,
        "phase": "acubliss_ui_canary",
        "units_completed": 2,
        "updated_at": "2026-07-18T12:00:00+00:00",
    }

    class Protocol:
        @staticmethod
        def read_active_run_record():
            return dict(pointer)

        @staticmethod
        def progress_path_for_nonce(nonce):
            assert nonce == pointer["run_nonce"]
            return Path("/private/progress.json")

        @staticmethod
        def read_progress_record(_path, *, expected_nonce):
            assert expected_nonce == pointer["run_nonce"]
            return dict(marker)

        @staticmethod
        def progress_is_stalled(_record):
            return stalled

    return Protocol


def test_regeneration_progress_requires_updater_checkpoint_beyond_wrapper_bootstrap(monkeypatch):
    wrapper = {"pid": 4241, "start_ticks": "111"}
    pointer = {
        "run_nonce": "a" * 32,
        "wrapper": wrapper,
        "child": {"pid": 4242, "start_ticks": "222"},
    }
    marker = {
        "version": 1,
        "run_nonce": "a" * 32,
        "seq": 1,
        "phase": "starting",
        "units_completed": 1,
        "updated_at": "2026-07-18T12:00:00+00:00",
    }
    monkeypatch.setattr(
        repair,
        "_waterlily_progress_protocol_module",
        lambda: _active_pointer_protocol(pointer, marker=marker, stalled=True),
    )

    assert repair._read_waterlily_regeneration_progress(wrapper) is None


def test_regeneration_progress_accepts_child_bootstrap_import_checkpoint(monkeypatch):
    wrapper = {"pid": 4241, "start_ticks": "111"}
    pointer = {
        "run_nonce": "a" * 32,
        "wrapper": wrapper,
        "child": {"pid": 4242, "start_ticks": "222"},
    }
    marker = {
        "version": 1,
        "run_nonce": "a" * 32,
        "seq": 2,
        "phase": "bootstrap_import",
        "units_completed": 2,
        "updated_at": "2026-07-18T12:00:00+00:00",
    }
    monkeypatch.setattr(
        repair,
        "_waterlily_progress_protocol_module",
        lambda: _active_pointer_protocol(pointer, marker=marker, stalled=True),
    )

    result = repair._read_waterlily_regeneration_progress(wrapper)

    assert result == {
        "version": 1,
        "run_nonce": "a" * 32,
        "seq": 2,
        "phase": "bootstrap_import",
        "units_completed": 2,
        "updated_at": "2026-07-18T12:00:00+00:00",
        "stalled": True,
    }


def test_waterlily_progress_protocol_loader_registers_dataclass_module_before_execution(monkeypatch, tmp_path):
    data_home = tmp_path / "data"
    waterlily_root = tmp_path / "waterlily"
    script = waterlily_root / "scripts" / "nightly_progress.py"
    script.parent.mkdir(parents=True)
    progress_root = data_home / "logs" / "waterlily_nightly_reports" / "progress"
    script.write_text(
        "\n".join([
            "from dataclasses import dataclass",
            "from pathlib import Path",
            f"PROGRESS_ROOT = Path({str(progress_root)!r})",
            "@dataclass(frozen=True)",
            "class NightlyProgressReporter:",
            "    nonce: str",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "VESSENCE_DATA_HOME", data_home)
    monkeypatch.setenv("JANE_WATERLILY_PROJECT_ROOT", str(waterlily_root))

    protocol = repair._waterlily_progress_protocol_module()

    assert protocol is not None
    assert protocol.NightlyProgressReporter("a" * 32).nonce == "a" * 32


def test_resume_adopts_exact_live_updater_after_wrapper_death_without_parallel_repair(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    updater_ticks, _state = observed
    wrapper = {"pid": 999991, "start_ticks": "123"}
    updater = {"pid": os.getpid(), "start_ticks": updater_ticks}
    pointer = {"run_nonce": "a" * 32, "wrapper": wrapper, "child": updater}
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "wrapper-died.json"
    incident_path.write_text(
        json.dumps({
            "id": "wrapper-died",
            "source": "waterlily_nightly_reports",
            "project_root": str(waterlily_root),
            "status": "repair_retrying",
            "tags": ["critical-auto-repair"],
            "payload": {"auto_repair_priority": "critical"},
            # The repair worker itself is deliberately live: adoption must
            # prevent a new wrapper even before that parent sees W's exit.
            "repair_worker": {
                "pid": os.getpid(),
                "start_ticks": updater_ticks,
                "regeneration_child": wrapper,
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "_waterlily_progress_protocol_module", lambda: _active_pointer_protocol(pointer))
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: True)
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("a proven live updater must block a replacement repair"),
    )

    assert repair.resume_critical_repairs() == 0
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_regeneration_orphan"] == {
        "version": 1,
        "wrapper": wrapper,
        "updater": updater,
    }

    observed_orphans = []
    monkeypatch.setattr(
        repair,
        "_observe_stalled_orphaned_regeneration",
        lambda path, orphan: observed_orphans.append((path, orphan)) or "progressing",
    )
    assert repair.resume_critical_repairs() == 0
    assert observed_orphans == [
        (incident_path, {"version": 1, "wrapper": wrapper, "updater": updater})
    ]


def test_resume_defers_mismatched_live_active_pointer_without_adoption(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    wrapper = {"pid": 999991, "start_ticks": "123"}
    pointer = {
        "run_nonce": "a" * 32,
        "wrapper": {"pid": 999992, "start_ticks": "456"},
        "child": {"pid": os.getpid(), "start_ticks": repair._process_start_ticks_and_state(os.getpid())[0]},
    }
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "pointer-mismatch.json"
    incident_path.write_text(
        json.dumps({
            "id": "pointer-mismatch",
            "source": "waterlily_nightly_reports",
            "project_root": str(waterlily_root),
            "status": "repair_retrying",
            "tags": ["critical-auto-repair"],
            "payload": {"auto_repair_priority": "critical"},
            "repair_worker": {"pid": 999999, "start_ticks": "1", "regeneration_child": wrapper},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "_waterlily_progress_protocol_module", lambda: _active_pointer_protocol(pointer))
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: False)
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("an unrelated live active pointer must block replacement"),
    )

    assert repair.resume_critical_repairs() == 0
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert "repair_regeneration_orphan" not in stored
    assert stored["repair_active_run_pointer_state"] == "unowned_live"


def test_resume_clears_lost_adopted_updater_before_one_normal_repair(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "orphan-finished.json"
    incident_path.write_text(
        json.dumps({
            "id": "orphan-finished",
            "source": "waterlily_nightly_reports",
            "project_root": str(waterlily_root),
            "status": "repair_retrying",
            "tags": ["critical-auto-repair"],
            "payload": {"auto_repair_priority": "critical"},
            "repair_worker": {"pid": 999999, "start_ticks": "1", "regeneration_child": {"pid": 999998, "start_ticks": "2"}},
            "repair_regeneration_orphan": {
                "version": 1,
                "wrapper": {"pid": 999998, "start_ticks": "2"},
                "updater": {"pid": 999997, "start_ticks": "3"},
            },
        }),
        encoding="utf-8",
    )
    launches = []
    monkeypatch.setattr(repair, "_waterlily_scheduler_lock_is_held", lambda: False)
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: launches.append((command, kwargs)))

    assert repair.resume_critical_repairs() == 1
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_regeneration_orphan"] is None
    assert len(launches) == 1


def _stalled_progress(*, seq=1, units=1, nonce="a" * 32):
    return {
        "version": 1,
        "run_nonce": nonce,
        "seq": seq,
        "phase": "acubliss_ui_canary",
        "units_completed": units,
        "updated_at": "2026-07-18T12:00:00+00:00",
        "stalled": True,
    }


def test_stalled_regeneration_requires_two_identical_safe_observations_before_one_signal(monkeypatch, tmp_path):
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    lease = {"pid": 4242, "start_ticks": "123"}
    signals = []
    monkeypatch.setattr(repair, "_read_waterlily_regeneration_progress", lambda _lease: _stalled_progress())
    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda _lease: 4242)
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "candidate"
    assert signals == []
    first = json.loads(incident_path.read_text(encoding="utf-8"))["repair_regeneration_watchdog"]
    assert first["state"] == "candidate"
    assert first["phase"] == "acubliss_ui_canary"
    assert first["units_completed"] == 1
    assert "patient" not in json.dumps(first).lower()

    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "termination_requested"
    assert signals == [(4242, signal.SIGTERM)]
    second = json.loads(incident_path.read_text(encoding="utf-8"))["repair_regeneration_watchdog"]
    assert second["state"] == "termination_requested"

    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "already_requested"
    assert signals == [(4242, signal.SIGTERM)]


def test_orphaned_updater_watchdog_requires_exact_wrapper_and_updater_pointer(monkeypatch, tmp_path):
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    wrapper = {"pid": 4241, "start_ticks": "111"}
    updater = {"pid": 4242, "start_ticks": "222"}
    pointer = {"run_nonce": "a" * 32, "wrapper": wrapper, "child": updater}
    orphan = {"version": 1, "wrapper": wrapper, "updater": updater}
    signals = []
    monkeypatch.setattr(
        repair,
        "_waterlily_progress_protocol_module",
        lambda: _active_pointer_protocol(pointer, stalled=True),
    )
    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda lease: int(lease["pid"]))
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    assert repair._observe_stalled_orphaned_regeneration(incident_path, orphan) == "candidate"
    assert repair._observe_stalled_orphaned_regeneration(incident_path, orphan) == "termination_requested"
    assert signals == [(4242, signal.SIGTERM)]

    # A pointer from another updater cannot be used to signal this one.
    pointer["child"] = {"pid": 4243, "start_ticks": "333"}
    other_path = tmp_path / "other-incident.json"
    other_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    assert repair._observe_stalled_orphaned_regeneration(other_path, orphan) == "protocol_unavailable"
    assert signals == [(4242, signal.SIGTERM)]


def test_stalled_regeneration_progress_advance_resets_candidate_without_signal(monkeypatch, tmp_path):
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    lease = {"pid": 4242, "start_ticks": "123"}
    current = {"value": _stalled_progress(seq=1, units=1)}
    signals = []
    monkeypatch.setattr(repair, "_read_waterlily_regeneration_progress", lambda _lease: current["value"])
    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda _lease: 4242)
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "candidate"
    current["value"] = {**_stalled_progress(seq=2, units=2), "stalled": False}
    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "progressing"
    current["value"] = _stalled_progress(seq=2, units=2)
    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "candidate"
    assert signals == []
    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "termination_requested"
    assert signals == [(4242, signal.SIGTERM)]


def test_stalled_regeneration_missing_or_untrusted_marker_never_signals(monkeypatch, tmp_path):
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    signals = []
    monkeypatch.setattr(repair, "_read_waterlily_regeneration_progress", lambda _lease: None)
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    assert repair._observe_stalled_regeneration_child(
        incident_path,
        {"pid": 4242, "start_ticks": "123"},
    ) == "protocol_unavailable"
    assert signals == []
    assert "repair_regeneration_watchdog" not in json.loads(incident_path.read_text(encoding="utf-8"))


def test_stalled_regeneration_revalidates_child_group_before_signal(monkeypatch, tmp_path):
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps({"id": "safe", "status": "repair_retrying"}), encoding="utf-8")
    lease = {"pid": 4242, "start_ticks": "123"}
    signals = []
    monkeypatch.setattr(repair, "_read_waterlily_regeneration_progress", lambda _lease: _stalled_progress())
    monkeypatch.setattr(repair, "_verified_regeneration_child_group", lambda _lease: None)
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "candidate"
    assert repair._observe_stalled_regeneration_child(incident_path, lease) == "child_revalidation_failed"
    assert signals == []
    state = json.loads(incident_path.read_text(encoding="utf-8"))["repair_regeneration_watchdog"]
    assert state["state"] == "candidate"


def test_resume_critical_repairs_observes_live_verified_child_without_parallel_replacement(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    observed = repair._process_start_ticks_and_state(os.getpid())
    assert observed is not None
    start_ticks, _state = observed
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "live-child.json"
    incident_path.write_text(
        json.dumps({
            "id": "live-child",
            "source": "waterlily_nightly_reports",
            "project_root": str(waterlily_root),
            "status": "repair_retrying",
            "tags": ["critical-auto-repair"],
            "payload": {"auto_repair_priority": "critical"},
            "repair_worker": {
                "pid": 999999,
                "start_ticks": "1",
                "regeneration_child": {"pid": os.getpid(), "start_ticks": start_ticks},
            },
        }),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(repair, "_observe_stalled_regeneration_child", lambda path, lease: calls.append((path, lease)) or "progressing")
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("watchdog must not overlap a live regeneration child"),
    )

    assert repair.resume_critical_repairs() == 0
    assert calls == [(incident_path, {"pid": os.getpid(), "start_ticks": start_ticks})]


def test_resume_critical_repairs_does_not_duplicate_a_live_worker(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "live.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "live",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                "repair_worker": {"pid": 999, "start_ticks": "1"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repair, "_repair_worker_liveness", lambda _incident: "live")
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("watchdog must not launch a duplicate live worker"),
    )

    assert repair.resume_critical_repairs() == 0


def test_resume_critical_repairs_reclaims_lost_worker_without_killing_any_live_process(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "lost.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "lost",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                "repair_worker": {"pid": 999, "start_ticks": "1"},
            }
        ),
        encoding="utf-8",
    )
    launched = []
    monkeypatch.setattr(repair, "_repair_worker_liveness", lambda _incident: "lost")
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: launched.append((command, kwargs)))

    assert repair.resume_critical_repairs() == 1
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_worker"] is None
    assert stored["repair_worker_lost_reason"] == "lost"
    assert len(launched) == 1


def test_resume_critical_repairs_only_continues_a_stopped_worker(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    repair.INCIDENT_DIR.mkdir(parents=True)
    incident_path = repair.INCIDENT_DIR / "stopped.json"
    incident_path.write_text(
        json.dumps(
            {
                "id": "stopped",
                "source": "waterlily_nightly_reports",
                "project_root": str(waterlily_root),
                "status": "repair_retrying",
                "tags": ["critical-auto-repair"],
                "payload": {"auto_repair_priority": "critical"},
                "repair_worker": {"pid": 4242, "start_ticks": "1"},
            }
        ),
        encoding="utf-8",
    )
    signals = []
    monkeypatch.setattr(repair, "_repair_worker_liveness", lambda _incident: "stopped")
    monkeypatch.setattr(repair.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("stopped worker should be continued, not replaced"),
    )

    assert repair.resume_critical_repairs() == 0
    assert signals == [(4242, signal.SIGCONT)]
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_worker_watchdog_action"] == "continued_stopped_worker"


def test_regeneration_polls_and_heartbeats_without_a_wall_clock_timeout(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    script = waterlily_root / "scripts" / "run_nightly_current_month_reports.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub", encoding="utf-8")

    class Process:
        def __init__(self):
            self.returncodes = [None, 0]

        def poll(self):
            return self.returncodes.pop(0)

    calls = []
    sleeps = []
    monkeypatch.setattr(repair, "_ACTIVE_REPAIR_INCIDENT_PATH", incident_path)
    monkeypatch.setattr(repair.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)) or Process())
    monkeypatch.setattr(repair.time, "sleep", sleeps.append)

    result = repair._run_waterlily_regeneration(
        waterlily_root,
        {"id": "safe-incident"},
        1,
        dt.datetime.now(dt.timezone.utc),
    )

    assert result["verification_reason"] == "summary_unavailable"
    assert len(calls) == 1
    assert calls[0][0] == [repair.PYTHON, str(script), "--full"]
    assert "timeout" not in calls[0][1]
    assert sleeps
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    worker = stored["repair_worker"]
    assert worker["phase"] == "regeneration"
    assert worker["phase_attempt"] == 1
    assert "heartbeat_at" in worker
    assert "command" not in worker


def test_regeneration_waits_for_adopted_updater_when_its_wrapper_exits(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    script = waterlily_root / "scripts" / "run_nightly_current_month_reports.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub", encoding="utf-8")

    class Process:
        pid = 4242

        @staticmethod
        def poll():
            return 1

    orphan = {
        "version": 1,
        "wrapper": {"pid": 4242, "start_ticks": "123"},
        "updater": {"pid": 4343, "start_ticks": "456"},
    }
    waited = []
    cleared = []
    monkeypatch.setattr(repair, "_ACTIVE_REPAIR_INCIDENT_PATH", incident_path)
    monkeypatch.setattr(repair.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(repair, "_process_start_ticks_and_state", lambda _pid: ("123", "R"))
    monkeypatch.setattr(repair, "_set_repair_regeneration_child", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(repair, "_adopt_active_regeneration_orphan", lambda *_args: ("adopted", orphan))
    monkeypatch.setattr(
        repair,
        "_wait_for_orphaned_regeneration_updater",
        lambda *args, **kwargs: waited.append((args, kwargs)) or "lost",
    )
    monkeypatch.setattr(
        repair,
        "_clear_regeneration_orphan",
        lambda *args, **kwargs: cleared.append((args, kwargs)) or True,
    )
    monkeypatch.setattr(repair, "_clear_repair_regeneration_child", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        repair,
        "_wait_for_scheduler_lock_release",
        lambda **_kwargs: pytest.fail("a proven updater must not be treated as an unknown lock holder"),
    )

    result = repair._run_waterlily_regeneration(
        waterlily_root,
        {"id": "safe-incident"},
        1,
        dt.datetime.now(dt.timezone.utc),
    )

    assert result["returncode"] == 0
    assert result["verification_reason"] == "summary_unavailable"
    assert len(waited) == 1
    assert len(cleared) == 1


def test_baseline_refresh_incident_never_auto_approves_ui_profile(monkeypatch, tmp_path):
    _vessence_home, _data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    script = waterlily_root / "scripts" / "run_nightly_current_month_reports.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub", encoding="utf-8")
    commands = []

    class Process:
        def poll(self):
            return 0

    monkeypatch.setattr(
        repair.subprocess,
        "Popen",
        lambda command, **kwargs: commands.append((command, kwargs)) or Process(),
    )
    monkeypatch.setattr(
        repair,
        "_verify_waterlily_summary",
        lambda *_args, **_kwargs: {"kind": "regeneration", "summary_fresh": True, "verification_reason": "verified"},
    )
    incident = {
        "id": "safe-incident",
        "payload": {
            "year": 2026,
            "month": 7,
            "extra": {"mode": "acubliss_ui_format_baseline_refresh"},
        },
    }

    result = repair._run_waterlily_regeneration(
        waterlily_root,
        incident,
        1,
        dt.datetime.now(dt.timezone.utc),
    )

    assert result["verification_reason"] == "verified"
    assert "recovery_preflight" not in result
    assert len(commands) == 1
    assert commands[0][0] == [repair.PYTHON, str(script), "--full"]
    assert commands[0][1]["start_new_session"] is True


def test_ui_baseline_incident_prompt_forbids_autonomous_profile_approval(tmp_path):
    prompt = repair._build_prompt(
        {
            "source": "waterlily_nightly_reports",
            "payload": {"extra": {"mode": "acubliss_ui_format_baseline_refresh"}},
        },
        tmp_path / "incident.json",
        tmp_path,
    )

    assert "Never approve or refresh a Waterlily AcuBliss/DASYS UI-format baseline" in prompt


def test_active_repair_nonzero_exit_forwards_only_safe_nightly_canary_handoff(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    script = waterlily_root / "scripts" / "run_nightly_current_month_reports.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub", encoding="utf-8")
    summary = data_home / "logs" / "waterlily_nightly_reports" / "latest.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(
        json.dumps(
            {
                "status": "failed",
                "mode": "incremental",
                "year": 2026,
                "month": 7,
                "error": "raw patient/vendor text must never be forwarded",
                "acubliss_patient_notes_ui_canary": {
                    "status": "failed",
                    "profile_version": 2,
                    "format_hash": "a" * 24,
                    "untrusted": "raw DOM text must never be forwarded",
                },
            }
        ),
        encoding="utf-8",
    )
    initial_mtime_ns = summary.stat().st_mtime_ns

    class Process:
        def poll(self):
            # Simulate the failed child rewriting the safe latest summary.
            os.utime(summary, ns=(initial_mtime_ns + 1_000_000_000, initial_mtime_ns + 1_000_000_000))
            return 1

    monkeypatch.setattr(repair.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    result = repair._run_waterlily_regeneration(
        waterlily_root,
        {"id": "safe-incident"},
        1,
        dt.datetime.now(dt.timezone.utc),
    )

    assert result["verification_reason"] == "runner_nonzero_exit"
    assert result["nightly_failure"] == {
        "summary_status": "failed",
        "mode": "incremental",
        "year": 2026,
        "month": 7,
        "canaries": [{
            "kind": "acubliss_patient_notes_ui_canary",
            "status": "failed",
            "profile_version": 2,
            "format_hash": "a" * 24,
        }],
    }
    safe = repair._safe_retry_context(result)
    serialized = json.dumps(safe)
    assert safe["nightly_failure"] == result["nightly_failure"]
    assert "raw patient" not in serialized
    assert "raw DOM" not in serialized


def test_critical_repair_finishes_when_a_fresh_report_already_recovered_the_incident(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, job_path = _critical_incident(tmp_path, waterlily_root, queue)
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    incident["created_at"] = "2026-07-18T12:00:00Z"
    incident_path.write_text(json.dumps(incident), encoding="utf-8")
    summary = data_home / "logs" / "waterlily_nightly_reports" / "latest.json"
    summary.parent.mkdir(parents=True)
    recovered_summary = _verified_nightly_summary()
    summary.write_text(json.dumps(recovered_summary), encoding="utf-8")

    report_path = Path(
        repair.run_repair(
            incident_path,
            completion_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not run")),
        )
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["status"] == "repair_finished"
    assert stored["repair_last_outcome"]["verification_reason"] == "verified"
    assert "Status: completed" in job_path.read_text(encoding="utf-8")
    assert "already verified" in report_path.read_text(encoding="utf-8")


def test_critical_repair_stops_on_acubliss_baseline_version_review_blocker(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, job_path = _critical_incident(tmp_path, waterlily_root, queue)
    backend_dir = waterlily_root / "backend"
    backend_dir.mkdir(parents=True)
    (backend_dir / "accounting_acubliss_exports.py").write_text(
        "ACUBLISS_UI_FORMAT_CONTRACT_VERSION = 3\n"
        "ACUBLISS_PATIENT_NOTES_UI_FORMAT_CONTRACT_VERSION = 2\n",
        encoding="utf-8",
    )
    nightly_dir = data_home / "logs" / "waterlily_nightly_reports"
    nightly_dir.mkdir(parents=True)
    (nightly_dir / "latest.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "mode": "full",
                "failure_stage": "checking AcuBliss UI format",
                "acubliss_ui_canary": {"status": "failed", "profile_version": 3},
            }
        ),
        encoding="utf-8",
    )
    (nightly_dir / "acubliss-ui-format-baseline.json").write_text(
        json.dumps({"version": 2}),
        encoding="utf-8",
    )
    (nightly_dir / "acubliss-patient-notes-ui-format-baseline.json").write_text(
        json.dumps({"version": 1}),
        encoding="utf-8",
    )

    report_path = Path(
        repair.run_repair(
            incident_path,
            completion_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("LLM should not run when reviewed baseline metadata is unsupported")
            ),
        )
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["status"] == "repair_failed"
    assert stored["repair_last_outcome"] == {
        "attempt": 0,
        "kind": "safety_stop",
        "verification_reason": "manual_review_required",
        "review_requirement": "acubliss_ui_baseline_version_unsupported",
        "expected_report_controls_version": 3,
        "actual_report_controls_version": 2,
        "expected_patient_notes_version": 2,
        "actual_patient_notes_version": 1,
    }
    assert "Status: blocked" in job_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    assert "manual_review_required" in report_text
    assert "acubliss_ui_baseline_version_unsupported" in report_text


def test_critical_repair_finishes_when_ui_incident_is_resolved_but_later_full_run_fails_elsewhere(
    monkeypatch,
    tmp_path,
):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, job_path = _critical_incident(tmp_path, waterlily_root, queue)
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    incident["created_at"] = "2026-07-18T15:06:13Z"
    incident["payload"]["stage"] = "refreshing AcuBliss UI format baseline"
    incident["payload"]["extra"] = {"mode": "acubliss_ui_format_baseline_refresh"}
    incident_path.write_text(json.dumps(incident), encoding="utf-8")

    backend_dir = waterlily_root / "backend"
    backend_dir.mkdir(parents=True)
    (backend_dir / "accounting_acubliss_exports.py").write_text(
        "ACUBLISS_UI_FORMAT_CONTRACT_VERSION = 3\n"
        "ACUBLISS_PATIENT_NOTES_UI_FORMAT_CONTRACT_VERSION = 2\n",
        encoding="utf-8",
    )
    nightly_dir = data_home / "logs" / "waterlily_nightly_reports"
    nightly_dir.mkdir(parents=True)
    (nightly_dir / "acubliss-ui-format-baseline.json").write_text(
        json.dumps({"version": 3}),
        encoding="utf-8",
    )
    (nightly_dir / "acubliss-patient-notes-ui-format-baseline.json").write_text(
        json.dumps({"version": 2}),
        encoding="utf-8",
    )
    (nightly_dir / "latest.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "mode": "full",
                "year": 2026,
                "month": 7,
                "started_at": "2026-07-20T00:42:52Z",
                "acubliss_ui_canary": {"status": "passed", "profile_version": 3},
                "acubliss_patient_notes_ui_canary": {"status": "passed", "profile_version": 2},
                "acubliss_package_detail_ui_canary": {"status": "passed", "profile_version": 3},
            }
        ),
        encoding="utf-8",
    )

    report_path = Path(
        repair.run_repair(
            incident_path,
            completion_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("LLM should not run after the captured UI issue is already resolved")
            ),
            regeneration_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("regeneration should not run after the captured UI issue is already resolved")
            ),
        )
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["status"] == "repair_finished"
    assert stored["repair_last_outcome"] == {
        "attempt": 0,
        "kind": "resolution",
        "summary_mode": "full",
        "summary_month": 7,
        "summary_status": "failed",
        "summary_year": 2026,
        "verification_reason": "later_full_run_failed_after_ui_recovery",
    }
    assert "Status: completed" in job_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    assert "later_full_run_failed_after_ui_recovery" in report_text
    assert "separate incident" in report_text


def test_critical_repair_notifies_vessence_once_after_codex_and_claude_exhaustion(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    announcements = []

    monkeypatch.setattr(
        repair,
        "_append_repair_failure_announcement",
        lambda path, task_id, message, created_at: announcements.append(
            {"path": path, "task_id": task_id, "message": message, "created_at": created_at}
        ),
    )

    def exhausted(*_args, **_kwargs):
        raise RepairProvidersExhausted([
            {"provider": "codex", "error_type": "ProviderCapacityResponse"},
            {"provider": "claude", "error_type": "RuntimeError"},
        ])

    repair.run_repair(
        incident_path,
        completion_fn=exhausted,
        sleep_fn=lambda _seconds: None,
        max_attempts=1,
    )
    # A restarted watchdog sees the persisted marker and does not announce
    # again for the same unresolved incident.
    repair.run_repair(
        incident_path,
        completion_fn=exhausted,
        sleep_fn=lambda _seconds: None,
        max_attempts=2,
    )

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert len(announcements) == 1
    assert announcements[0]["path"] == data_home / "data" / "jane_announcements.jsonl"
    assert announcements[0]["task_id"].startswith("self-healing-provider-failure-")
    assert announcements[0]["message"] == repair.REPAIR_PROVIDER_FAILURE_MESSAGE
    assert stored["status"] == "repair_retrying"
    assert "repair_provider_exhaustion_notified_at" in stored


def test_noncritical_repair_notifies_vessence_after_codex_and_claude_exhaustion(monkeypatch, tmp_path):
    vessence_home, data_home, _waterlily_root, _queue = _configure_paths(monkeypatch, tmp_path)
    incident_path = tmp_path / "generic-ui-incident.json"
    incident_path.write_text(
        json.dumps({
            "id": "generic-ui-incident",
            "source": "waterlily_vendor_automation",
            "project_root": str(vessence_home),
            "status": "captured",
            "tags": ["waterlily", "ui-contract"],
            "payload": {},
        }),
        encoding="utf-8",
    )
    announcements = []
    monkeypatch.setattr(
        repair,
        "_append_repair_failure_announcement",
        lambda path, task_id, message, created_at: announcements.append(
            {"path": path, "task_id": task_id, "message": message, "created_at": created_at}
        ),
    )

    def exhausted(*_args, **_kwargs):
        raise RepairProvidersExhausted([
            {"provider": "codex", "error_type": "ProviderCapacityResponse"},
            {"provider": "claude", "error_type": "RuntimeError"},
        ])

    repair.run_repair(incident_path, completion_fn=exhausted, max_attempts=1)

    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert len(announcements) == 1
    assert announcements[0]["path"] == data_home / "data" / "jane_announcements.jsonl"
    assert announcements[0]["message"] == repair.GENERIC_REPAIR_PROVIDER_FAILURE_MESSAGE
    assert stored["status"] == "repair_failed"
    assert stored["repair_provider_exhaustion_notification_state"] == "sent"


def test_provider_failure_notification_recovers_after_append_before_sent_marker(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    incident_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    original_write = repair._write_incident_update

    def fail_sent_marker(path, **updates):
        if updates.get("repair_provider_exhaustion_notification_state") == "sent":
            return False
        return original_write(path, **updates)

    monkeypatch.setattr(repair, "_write_incident_update", fail_sent_marker)
    assert repair._notify_repair_provider_exhaustion(
        incident_path,
        incident,
        critical_waterlily=True,
    ) is False

    announcement_path = data_home / "data" / "jane_announcements.jsonl"
    assert len(announcement_path.read_text(encoding="utf-8").splitlines()) == 1
    pending = json.loads(incident_path.read_text(encoding="utf-8"))
    assert pending["repair_provider_exhaustion_notification_state"] == "pending"

    monkeypatch.setattr(repair, "_write_incident_update", original_write)
    assert repair._notify_repair_provider_exhaustion(
        incident_path,
        incident,
        critical_waterlily=True,
    ) is True

    assert len(announcement_path.read_text(encoding="utf-8").splitlines()) == 1
    stored = json.loads(incident_path.read_text(encoding="utf-8"))
    assert stored["repair_provider_exhaustion_notification_state"] == "sent"


def test_provider_exhaustion_alert_is_new_for_a_later_incident_with_same_fingerprint(monkeypatch, tmp_path):
    _vessence_home, data_home, waterlily_root, queue = _configure_paths(monkeypatch, tmp_path)
    first_path, _job_path = _critical_incident(tmp_path, waterlily_root, queue)
    first = json.loads(first_path.read_text(encoding="utf-8"))
    second_path = tmp_path / "second-incident.json"
    second_path.write_text(json.dumps(first), encoding="utf-8")

    assert repair._notify_repair_provider_exhaustion(
        first_path,
        first,
        critical_waterlily=True,
    ) is True
    assert repair._notify_repair_provider_exhaustion(
        second_path,
        first,
        critical_waterlily=True,
    ) is True
    # The same incident file still has a persisted sent marker and cannot
    # create a duplicate announcement during watchdog retries.
    assert repair._notify_repair_provider_exhaustion(
        first_path,
        first,
        critical_waterlily=True,
    ) is False

    lines = [json.loads(line) for line in (data_home / "data" / "jane_announcements.jsonl").read_text().splitlines()]
    assert len(lines) == 2
    task_ids = {str(line["id"]) for line in lines}
    assert len(task_ids) == 2
    assert all(task_id.startswith("self-healing-provider-failure-") for task_id in task_ids)
