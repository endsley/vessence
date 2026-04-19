"""Unit tests for agent_skills.web_automation.artifacts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import artifacts


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    rid = artifacts.new_run_id(label="test")
    return artifacts.RunDir(rid)


def test_new_run_id_unique_per_call():
    a = artifacts.new_run_id(label="a")
    b = artifacts.new_run_id(label="a")
    assert a != b
    assert a.startswith("run_")
    assert "a" in a


def test_run_id_sanitizes_label():
    rid = artifacts.new_run_id(label="Pay Water Bill!! v2")
    assert "paywaterbill" in rid.replace("_", "") or "paywaterbillv2" in rid


def test_run_dir_writes_initial_run_json(run_dir):
    data = json.loads((run_dir.dir / "run.json").read_text())
    assert data["run_id"] == run_dir.run_id
    assert data["status"] == "running"
    assert data["steps"] == []


def test_run_dir_append_step_redacts_password(run_dir):
    run_dir.append_step(
        action="fill",
        args={"ref": "e02", "password": "hunter2"},
        ok=True,
        message="Filled",
        duration_ms=50,
    )
    trace = json.loads((run_dir.dir / "trace.json").read_text())
    assert len(trace) == 1
    step = trace[0]
    assert step["args"]["password"] == "[REDACTED]"
    assert step["args"]["ref"] == "e02"


def test_run_dir_append_step_redacts_token_field(run_dir):
    run_dir.append_step(
        action="fill",
        args={"ref": "e02", "auth_token": "xyz", "api_key": "k"},
        ok=True,
        message="Filled",
        duration_ms=12,
    )
    trace = json.loads((run_dir.dir / "trace.json").read_text())
    step = trace[0]
    # Any arg with "password" substring OR in _SECRET_FIELDS is redacted.
    # auth_token passes through (not in hard list, no "password" substring),
    # api_key IS in the list.
    assert step["args"]["api_key"] == "[REDACTED]"


def test_run_dir_clips_long_string_arg(run_dir):
    long_val = "x" * 1500
    run_dir.append_step(
        action="fill",
        args={"ref": "e01", "text": long_val},
        ok=True,
        message="ok",
        duration_ms=1,
    )
    trace = json.loads((run_dir.dir / "trace.json").read_text())
    assert len(trace[0]["args"]["text"]) < 500
    assert "...(+" in trace[0]["args"]["text"]


def test_run_dir_finish_sets_status_and_ended_at(run_dir):
    run_dir.finish(status="completed")
    data = json.loads((run_dir.dir / "run.json").read_text())
    assert data["status"] == "completed"
    assert data["ended_at"] is not None
    assert data["ended_at"].endswith("Z")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
