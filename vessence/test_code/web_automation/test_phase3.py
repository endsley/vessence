"""Phase 3 tests: workflow save / load / list / delete."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import workflow as wf


@pytest.fixture(autouse=True)
def _tmp_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    return tmp_path


def test_save_and_load_by_name():
    wid = wf.save(
        name="Pay Water Bill",
        description="Log in and pay",
        steps=[{"action": "navigate", "args": {"url": "https://citywater.com/login"}}],
    )
    assert wid.startswith("wf_")
    doc = wf.load("pay water bill")
    assert doc["name"] == "Pay Water Bill"
    assert doc["steps"][0]["action"] == "navigate"


def test_load_by_id():
    wid = wf.save(
        name="hello",
        description="",
        steps=[{"action": "status", "args": {}}],
    )
    doc = wf.load(wid)
    assert doc["id"] == wid


def test_save_reuses_id_for_same_name():
    w1 = wf.save(name="a", description="", steps=[{"action": "status"}])
    w2 = wf.save(name="A", description="updated", steps=[{"action": "snapshot"}])
    assert w1 == w2
    doc = wf.load("a")
    assert doc["description"] == "updated"
    assert doc["steps"][0]["action"] == "snapshot"


def test_list_workflows():
    wf.save(name="one", description="", steps=[{"action": "status"}])
    wf.save(name="two", description="", steps=[{"action": "status"}])
    names = sorted(w.name for w in wf.list_workflows())
    assert names == ["one", "two"]


def test_delete_is_soft():
    wid = wf.save(name="ephemeral", description="", steps=[{"action": "status"}])
    wf.delete("ephemeral")
    with pytest.raises(wf.WorkflowNotFound):
        wf.load("ephemeral")
    wf.restore(wid)
    doc = wf.load("ephemeral")
    assert doc["id"] == wid


def test_missing_raises():
    with pytest.raises(wf.WorkflowNotFound):
        wf.load("no-such-thing")


def test_save_rejects_step_without_action():
    with pytest.raises(ValueError):
        wf.save(name="bad", description="", steps=[{"args": {}}])


def test_save_rejects_empty_name():
    with pytest.raises(ValueError):
        wf.save(name="", description="", steps=[{"action": "status"}])


def test_rebuild_index_recovers():
    wf.save(name="keep me", description="", steps=[{"action": "status"}])
    # Nuke the index — rebuild should recover.
    idx_path = wf._index_path()
    idx_path.unlink()
    n = wf.rebuild_index()
    assert n == 1
    doc = wf.load("keep me")
    assert doc["name"] == "keep me"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
