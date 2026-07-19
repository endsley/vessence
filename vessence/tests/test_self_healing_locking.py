import fcntl
import importlib
import json
import time

from agent_skills import self_healing_repair
from agent_skills import self_healing_storage as storage


def _reloaded_self_healing(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_AUTO_REPAIR", "0")

    import agent_skills.self_healing as self_healing

    return importlib.reload(self_healing), home, data


def test_capture_defers_promptly_when_state_lock_is_held(tmp_path, monkeypatch):
    self_healing, _home, data = _reloaded_self_healing(tmp_path, monkeypatch)
    lock_path = data / "self_healing" / "state.lock"
    lock_path.parent.mkdir(parents=True)

    with lock_path.open("a+") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX)
        try:
            started = time.monotonic()
            captured = self_healing.capture_report(
                source="lock_test",
                category="safe_test",
                message="state lock held",
                auto_repair=False,
            )
            assert time.monotonic() - started < 1
        finally:
            fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)

    assert captured is not None
    assert captured["status"] == "deferred"
    assert not list((data / "self_healing" / "incidents").glob("*.json"))
    spooled = list((data / "self_healing" / "deferred_captures").glob("*.json"))
    assert len(spooled) == 1
    assert spooled[0].stat().st_mode & 0o777 == 0o600
    assert lock_path.stat().st_mode & 0o777 == 0o600

    assert self_healing.drain_deferred_captures() == 1
    assert len(list((data / "self_healing" / "incidents").glob("*.json"))) == 1


def test_noncritical_launch_returns_promptly_when_state_lock_is_held(tmp_path, monkeypatch):
    self_healing, _home, data = _reloaded_self_healing(tmp_path, monkeypatch)
    incident_path = data / "incident.json"
    storage.atomic_write_private_json(incident_path, {"id": "safe", "tags": []})
    lock_path = data / "self_healing" / "state.lock"
    lock_path.parent.mkdir(parents=True)
    monkeypatch.setattr(
        self_healing.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("repair must be deferred")),
    )

    with lock_path.open("a+") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX)
        try:
            started = time.monotonic()
            self_healing._maybe_launch_auto_repair(incident_path)
            assert time.monotonic() - started < 1
        finally:
            fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)


def test_repair_incident_update_returns_safe_failure_when_private_json_lock_is_held(tmp_path):
    incident_path = tmp_path / "incident.json"
    storage.atomic_write_private_json(incident_path, {"id": "safe", "status": "captured"})
    lock_path = incident_path.with_suffix(incident_path.suffix + ".lock")

    with lock_path.open("a+") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX)
        try:
            started = time.monotonic()
            assert self_healing_repair._write_incident_update(incident_path, status="repair_retrying") is False
            assert time.monotonic() - started < 1
        finally:
            fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)

    assert json.loads(incident_path.read_text(encoding="utf-8")) == {
        "id": "safe",
        "status": "captured",
    }


def test_active_critical_waterlily_incident_dedupes_after_ordinary_rate_window(tmp_path, monkeypatch):
    self_healing, _home, data = _reloaded_self_healing(tmp_path, monkeypatch)
    incident_dir = data / "self_healing" / "incidents"
    incident_dir.mkdir(parents=True)
    existing_path = incident_dir / "existing.json"
    existing = {
        "id": "waterlily_nightly_reports_same",
        "fingerprint": "same",
        "source": "waterlily_nightly_reports",
        "category": "nightly_accounting_report_failure",
        "status": "repair_retrying",
        "payload": {"auto_repair_priority": "critical"},
        "tags": ["critical-auto-repair"],
    }
    storage.atomic_write_private_json(existing_path, existing)
    storage.atomic_write_private_json(
        self_healing.STATE_PATH,
        {
            "fingerprints": {
                "same": {
                    "count": 3,
                    "last_seen_ts": 1.0,
                    "last_seen_at": "2026-01-01T00:00:00+00:00",
                    "first_seen_at": "2026-01-01T00:00:00+00:00",
                    "incident_path": str(existing_path),
                    "job_path": str(tmp_path / "old-job.md"),
                    "source": "waterlily_nightly_reports",
                    "category": "nightly_accounting_report_failure",
                }
            }
        },
    )
    recurrence = {
        "id": "waterlily_nightly_reports_same",
        "fingerprint": "same",
        "source": "waterlily_nightly_reports",
        "category": "nightly_accounting_report_failure",
        "status": "captured",
        "created_at": "2026-07-18T21:00:00+00:00",
        "project_root": str(tmp_path / "waterlily"),
        "payload": {"auto_repair_priority": "critical"},
        "tags": ["critical-auto-repair"],
    }

    result = self_healing._record_incident(recurrence, auto_repair=False)

    assert result is not None
    assert result["deduped"] is True
    assert result["incident_path"] == str(existing_path)
    assert len(list(incident_dir.glob("*.json"))) == 1
    state = json.loads(self_healing.STATE_PATH.read_text(encoding="utf-8"))
    assert state["fingerprints"]["same"]["count"] == 4
    assert state["fingerprints"]["same"]["incident_path"] == str(existing_path)
