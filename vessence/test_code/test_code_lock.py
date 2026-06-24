from __future__ import annotations

import os
from pathlib import Path

from agent_skills import code_lock


def test_known_project_aliases_use_independent_lock_files(monkeypatch, tmp_path):
    monkeypatch.setattr(code_lock, "LOCK_DIR", tmp_path)

    education = code_lock.resolve_lock_scope("education")
    waterlily = code_lock.resolve_lock_scope("waterlily")
    vessence = code_lock.resolve_lock_scope("vessence")

    assert education.name == "education"
    assert waterlily.name == "waterlily"
    assert vessence.name == "vessence"
    assert len({education.lock_file, waterlily.lock_file, vessence.lock_file}) == 3


def test_cwd_under_known_project_infers_scope(monkeypatch, tmp_path):
    project_root = tmp_path / "code" / "chieh_class_v2"
    nested = project_root / "app" / "routers"
    nested.mkdir(parents=True)
    monkeypatch.setattr(
        code_lock,
        "_known_project_roots",
        lambda: {
            "education": project_root.resolve(),
            "waterlily": (tmp_path / "code" / "waterlily").resolve(),
            "vessence": (tmp_path / "ambient" / "vessence").resolve(),
        },
    )
    monkeypatch.setattr(code_lock, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.chdir(nested)

    scope = code_lock.resolve_lock_scope()

    assert scope.name == "education"
    assert scope.lock_file.name == "code_edit_education.lock"


def test_project_locks_do_not_block_each_other(monkeypatch, tmp_path):
    monkeypatch.setattr(code_lock, "LOCK_DIR", tmp_path)
    edu_fd = code_lock.acquire_lock("test-edu", timeout=0.1, project="education")
    water_fd = code_lock.acquire_lock("test-water", timeout=0.1, project="waterlily")
    try:
        edu_holder = code_lock.who_holds_lock("education")
        water_holder = code_lock.who_holds_lock("waterlily")
        assert edu_holder and edu_holder["agent"] == "test-edu"
        assert water_holder and water_holder["agent"] == "test-water"
        assert code_lock.who_holds_lock("vessence") is None
    finally:
        code_lock.release_lock(water_fd)
        code_lock.release_lock(edu_fd)


def test_env_var_can_select_project(monkeypatch, tmp_path):
    monkeypatch.setattr(code_lock, "LOCK_DIR", tmp_path)
    monkeypatch.setenv("JANE_CODE_LOCK_PROJECT", "waterlily")

    scope = code_lock.resolve_lock_scope()

    assert scope.name == "waterlily"
    assert Path(scope.lock_file).name == "code_edit_waterlily.lock"
