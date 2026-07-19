from __future__ import annotations

from contextlib import contextmanager

import pytest

from agent_skills import waterlily_ui_baseline_approval as approval


def test_approval_requires_full_hash_and_reviewer_before_observation(monkeypatch):
    observed = []
    committed = []

    with pytest.raises(approval.BaselineApprovalError, match="full reviewed profile SHA-256"):
        approval.approve_reviewed_waterlily_profile(
            kind="dasys-live-era",
            reviewed_profile_sha256="short",
            reviewed_by="",
            observe=lambda: observed.append(True) or {"safe": "profile"},
            commit=lambda *_args: committed.append(True),
        )

    assert observed == []
    assert committed == []


def test_approval_observes_and_commits_inside_waterlily_lock(monkeypatch):
    events = []
    profile = {"source_mode": "live_era", "tables": 2}

    @contextmanager
    def fake_lock(agent_name, *, project):
        events.append(("lock-enter", agent_name, project))
        yield
        events.append(("lock-exit", agent_name, project))

    monkeypatch.setattr(approval, "code_edit_lock", fake_lock)

    def observe():
        events.append("observe")
        return profile

    def commit(observed_profile, metadata):
        events.append(("commit", observed_profile, metadata))

    result = approval.approve_reviewed_waterlily_profile(
        kind="dasys-live-era",
        reviewed_profile_sha256=approval.canonical_profile_sha256(profile),
        reviewed_by="Chieh",
        observe=observe,
        commit=commit,
    )

    assert events[0] == ("lock-enter", "waterlily-ui-baseline-approval", "waterlily")
    assert events[1] == "observe"
    assert events[2][0] == "commit"
    assert events[2][1] == profile
    assert events[2][2]["reviewed_by"] == "Chieh"
    assert events[3] == ("lock-exit", "waterlily-ui-baseline-approval", "waterlily")
    assert result == {
        "status": "approved",
        "kind": "dasys-live-era",
        "observed_profile_sha256": approval.canonical_profile_sha256(profile),
    }


def test_approval_rejects_stale_hash_without_commit(monkeypatch):
    @contextmanager
    def fake_lock(*_args, **_kwargs):
        yield

    monkeypatch.setattr(approval, "code_edit_lock", fake_lock)
    committed = []

    with pytest.raises(approval.BaselineApprovalError, match="does not match"):
        approval.approve_reviewed_waterlily_profile(
            kind="dasys-monthly-pdf",
            reviewed_profile_sha256="0" * 64,
            reviewed_by="Chieh",
            observe=lambda: {"safe": "new-profile"},
            commit=lambda *_args: committed.append(True),
        )

    assert committed == []


def test_autonomous_repair_cannot_approve_baseline(monkeypatch):
    monkeypatch.setenv("JANE_SELF_HEAL_ACTIVE", "1")
    observed = []

    with pytest.raises(approval.BaselineApprovalError, match="Autonomous repair"):
        approval.approve_reviewed_waterlily_profile(
            kind="dasys-files-tab",
            reviewed_profile_sha256="0" * 64,
            reviewed_by="Chieh",
            observe=lambda: observed.append(True) or {"safe": "profile"},
            commit=lambda *_args: pytest.fail("must not commit"),
        )

    assert observed == []
