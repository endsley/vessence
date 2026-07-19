import importlib
import json
from pathlib import Path


def test_capture_exception_creates_incident_and_job(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_AUTO_REPAIR", "0")

    import agent_skills.self_healing as self_healing

    self_healing = importlib.reload(self_healing)
    try:
        raise ValueError("broken route")
    except ValueError as exc:
        incident = self_healing.capture_exception(
            source="test_app",
            exc=exc,
            request_info={"method": "GET", "path": "/boom"},
            project_root=str(home),
        )

    assert incident is not None
    assert incident["deduped"] is False
    assert incident["exception"]["type"] == "ValueError"
    assert (data / "self_healing" / "incidents").exists()
    job_path = home / "configs" / "job_queue" / "job_001_self_heal_test_app_exception.md"
    assert job_path.exists()
    assert "Self-heal test_app" in job_path.read_text()


def test_capture_exception_dedupes_recent_fingerprint(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_AUTO_REPAIR", "0")

    import agent_skills.self_healing as self_healing

    self_healing = importlib.reload(self_healing)

    def capture_once():
        try:
            raise RuntimeError("same failure")
        except RuntimeError as exc:
            return self_healing.capture_exception(
                source="test_app",
                exc=exc,
                request_info={"method": "GET", "path": "/same"},
                project_root=str(home),
            )

    first = capture_once()
    second = capture_once()

    assert first is not None and second is not None
    assert first["deduped"] is False
    assert second["deduped"] is True
    jobs = list((home / "configs" / "job_queue").glob("job_*.md"))
    assert len(jobs) == 1
    state = json.loads((data / "self_healing" / "state.json").read_text())
    assert next(iter(state["fingerprints"].values()))["count"] == 2


def test_terminal_repair_recurrence_creates_a_fresh_incident_inside_rate_limit(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_AUTO_REPAIR", "0")

    import agent_skills.self_healing as self_healing

    self_healing = importlib.reload(self_healing)

    def capture_once():
        try:
            raise RuntimeError("same failure")
        except RuntimeError as exc:
            return self_healing.capture_exception(
                source="test_app",
                exc=exc,
                request_info={"method": "GET", "path": "/same"},
                project_root=str(home),
            )

    first = capture_once()
    assert first is not None
    first_path = Path(first["incident_path"])
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    first_payload["status"] = "repair_finished"
    first_path.write_text(json.dumps(first_payload), encoding="utf-8")

    second = capture_once()

    assert second is not None
    assert second["deduped"] is False
    assert Path(second["incident_path"]) != first_path
    assert Path(second["job_path"]) != Path(first["job_path"])
    state = json.loads((data / "self_healing" / "state.json").read_text())
    record = next(iter(state["fingerprints"].values()))
    assert record["incident_path"] == second["incident_path"]
    assert record["count"] == 2


def test_capture_failure_spools_then_watchdog_replays_private_incident(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_AUTO_REPAIR", "0")

    import agent_skills.self_healing as self_healing

    self_healing = importlib.reload(self_healing)
    original_record = self_healing._record_incident
    monkeypatch.setattr(
        self_healing,
        "_record_incident",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("state temporarily unavailable")),
    )

    deferred = self_healing.capture_report(
        source="test_app",
        category="safe_test",
        message="safe failure",
        payload={"exception_class": "SafeError"},
        auto_repair=False,
    )

    assert deferred == {
        "id": deferred["id"],
        "status": "deferred",
        "deduped": False,
        "occurrence_count": 0,
    }
    spooled = list((data / "self_healing" / "deferred_captures").glob("*.json"))
    assert len(spooled) == 1
    assert spooled[0].stat().st_mode & 0o777 == 0o600

    monkeypatch.setattr(self_healing, "_record_incident", original_record)
    assert self_healing.drain_deferred_captures() == 1
    assert not list((data / "self_healing" / "deferred_captures").glob("*.json"))
    assert len(list((data / "self_healing" / "incidents").glob("*.json"))) == 1


def test_active_repair_does_not_spool_capture_recursively(tmp_path, monkeypatch):
    home = tmp_path / "vessence"
    data = tmp_path / "data"
    (home / "configs" / "job_queue").mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_HOME", str(home))
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data))
    monkeypatch.setenv("JANE_SELF_HEALING", "1")
    monkeypatch.setenv("JANE_SELF_HEAL_ACTIVE", "1")

    import agent_skills.self_healing as self_healing

    self_healing = importlib.reload(self_healing)
    assert self_healing.capture_report(
        source="test_app",
        category="safe_test",
        message="safe failure",
    ) is None
    assert not (data / "self_healing" / "deferred_captures").exists()
