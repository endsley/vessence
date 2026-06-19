import importlib
import json


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
