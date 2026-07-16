import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent_skills import code_coordination as coordination
from agent_skills import code_lock


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path, monkeypatch):
    project_root = tmp_path / "shared-project"
    project_root.mkdir()
    (project_root / ".git").mkdir()
    (project_root / "backend").mkdir()
    (project_root / "frontend").mkdir()
    monkeypatch.setattr(code_lock, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(
        code_lock,
        "LEGACY_LOCK_FILE",
        tmp_path / "locks" / "code_edit.lock",
    )
    monkeypatch.setattr(code_lock, "LOCK_FILE", code_lock.LEGACY_LOCK_FILE)
    return project_root, tmp_path / "coordination.db"


def test_many_sessions_can_claim_non_overlapping_files(project):
    project_root, db_path = project

    for index in range(25):
        coordination.post_task(
            f"Worker {index}",
            project=project_root,
            files=[f"backend/worker_{index}.py"],
            session_id=f"session-{index}",
            db_path=db_path,
        )

    snapshot = coordination.board_snapshot(
        project=project_root,
        session_id="observer",
        db_path=db_path,
    )

    assert len(snapshot["work_items"]) == 25
    assert {
        item["claims"][0]["path"]
        for item in snapshot["work_items"]
    } == {f"backend/worker_{index}.py" for index in range(25)}


def test_many_sessions_can_claim_non_overlapping_files_concurrently(project):
    project_root, db_path = project
    coordination.board_snapshot(
        project=project_root,
        session_id="initializer",
        db_path=db_path,
    )
    barrier = threading.Barrier(20)

    def post(index):
        barrier.wait()
        return coordination.post_task(
            f"Concurrent worker {index}",
            project=project_root,
            files=[f"frontend/worker_{index}.js"],
            session_id=f"concurrent-{index}",
            db_path=db_path,
        )

    with ThreadPoolExecutor(max_workers=20) as executor:
        items = list(executor.map(post, range(20)))

    assert len(items) == 20
    assert all(item["status"] == "active" for item in items)


def test_same_file_concurrent_race_allows_exactly_one_claim(project):
    project_root, db_path = project
    coordination.board_snapshot(
        project=project_root,
        session_id="initializer",
        db_path=db_path,
    )
    barrier = threading.Barrier(2)

    def race(session_id):
        barrier.wait()
        try:
            coordination.post_task(
                "Race for shared file",
                project=project_root,
                files=["backend/race.py"],
                session_id=session_id,
                db_path=db_path,
            )
            return "claimed"
        except coordination.ClaimConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(race, ["racer-one", "racer-two"]))

    assert sorted(outcomes) == ["claimed", "conflict"]


def test_overlapping_file_claim_fails_fast_with_owner_details(project):
    project_root, db_path = project
    coordination.post_task(
        "Edit auth backend",
        project=project_root,
        files=["backend/auth.py"],
        session_id="first-session",
        agent="first-codex",
        db_path=db_path,
    )

    with pytest.raises(coordination.ClaimConflict) as exc_info:
        coordination.post_task(
            "Refactor auth backend",
            project=project_root,
            files=["backend/auth.py"],
            session_id="second-session",
            agent="second-codex",
            db_path=db_path,
        )

    assert exc_info.value.conflicts == [
        {
            "path": "backend/auth.py",
            "kind": "file",
            "session_id": "first-session",
            "agent": "first-codex",
            "task": "Edit auth backend",
        }
    ]
    second = coordination.work_item_details(
        project_root,
        "second-session",
        db_path=db_path,
    )
    assert second["status"] == "blocked"
    assert "first-codex" in second["note"]


def test_directory_claim_blocks_descendants_but_not_siblings(project):
    project_root, db_path = project
    coordination.post_task(
        "Refactor backend",
        project=project_root,
        files=["backend/**"],
        session_id="backend-session",
        db_path=db_path,
    )

    with pytest.raises(coordination.ClaimConflict):
        coordination.post_task(
            "Edit backend route",
            project=project_root,
            files=["backend/routes.py"],
            session_id="route-session",
            db_path=db_path,
        )

    frontend = coordination.post_task(
        "Edit frontend",
        project=project_root,
        files=["frontend/app.js"],
        session_id="frontend-session",
        db_path=db_path,
    )
    assert frontend["claims"] == [{"path": "frontend/app.js", "kind": "file"}]


def test_finishing_task_releases_claim_for_another_session(project):
    project_root, db_path = project
    coordination.post_task(
        "First edit",
        project=project_root,
        files=["backend/shared.py"],
        session_id="first-session",
        db_path=db_path,
    )

    assert coordination.finish_task(
        project=project_root,
        session_id="first-session",
        result="done",
        db_path=db_path,
    )

    second = coordination.post_task(
        "Second edit",
        project=project_root,
        files=["backend/shared.py"],
        session_id="second-session",
        db_path=db_path,
    )
    assert second["status"] == "active"
    with sqlite3.connect(db_path) as connection:
        released_at = connection.execute(
            """
            SELECT released_at FROM code_claims c
            JOIN code_work_items w ON w.id=c.work_item_id
            WHERE w.session_id='first-session'
            """
        ).fetchone()[0]
    assert released_at is not None


def test_reposting_task_replaces_old_claims(project):
    project_root, db_path = project
    coordination.post_task(
        "First task",
        project=project_root,
        files=["backend/old.py"],
        session_id="same-session",
        db_path=db_path,
    )

    item = coordination.post_task(
        "Replacement task",
        project=project_root,
        files=["backend/new.py"],
        session_id="same-session",
        db_path=db_path,
    )

    assert item["task"] == "Replacement task"
    assert item["claims"] == [{"path": "backend/new.py", "kind": "file"}]


def test_claim_addition_release_and_message_flow(project):
    project_root, db_path = project
    coordination.post_task(
        "Incremental edit",
        project=project_root,
        files=["backend/one.py"],
        session_id="first-session",
        db_path=db_path,
    )
    item = coordination.claim_files(
        ["backend/two.py"],
        project=project_root,
        session_id="first-session",
        db_path=db_path,
    )
    assert [claim["path"] for claim in item["claims"]] == [
        "backend/one.py",
        "backend/two.py",
    ]

    assert coordination.release_files(
        ["backend/one.py"],
        project=project_root,
        session_id="first-session",
        db_path=db_path,
    ) == 1
    coordination.post_message(
        "I released backend/one.py",
        project=project_root,
        recipient_session_id="second-session",
        session_id="first-session",
        db_path=db_path,
    )
    snapshot = coordination.board_snapshot(
        project=project_root,
        session_id="second-session",
        db_path=db_path,
    )
    assert snapshot["work_items"][0]["claims"] == [
        {"path": "backend/two.py", "kind": "file"}
    ]
    assert snapshot["messages"][0]["body"] == "I released backend/one.py"


def test_stale_claims_are_pruned_and_stop_blocking(project, monkeypatch):
    project_root, db_path = project
    coordination.post_task(
        "Abandoned edit",
        project=project_root,
        files=["backend/stale.py"],
        session_id="stale-session",
        db_path=db_path,
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE code_work_items SET heartbeat_at=0 WHERE session_id='stale-session'"
        )
    monkeypatch.setattr(coordination, "STALE_AFTER_SECONDS", 300)

    replacement = coordination.post_task(
        "Replacement edit",
        project=project_root,
        files=["backend/stale.py"],
        session_id="replacement-session",
        db_path=db_path,
    )

    assert replacement["status"] == "active"
    with sqlite3.connect(db_path) as connection:
        stale_released_at = connection.execute(
            """
            SELECT released_at FROM code_claims c
            JOIN code_work_items w ON w.id=c.work_item_id
            WHERE w.session_id='stale-session'
            """
        ).fetchone()[0]
    assert stale_released_at is not None


def test_claim_rejects_paths_outside_project(project):
    project_root, db_path = project

    with pytest.raises(coordination.CoordinationError, match="outside project root"):
        coordination.post_task(
            "Unsafe claim",
            project=project_root,
            files=["../outside.py"],
            session_id="session",
            db_path=db_path,
        )


def test_legacy_exclusive_lock_blocks_new_scoped_claims(project):
    project_root, db_path = project
    descriptor = code_lock.acquire_lock("legacy-agent", project=project_root)
    try:
        with pytest.raises(coordination.LegacyLockConflict, match="legacy-agent"):
            coordination.post_task(
                "Scoped edit",
                project=project_root,
                files=["backend/file.py"],
                session_id="scoped-session",
                db_path=db_path,
            )
    finally:
        code_lock.release_lock(descriptor)


def test_old_global_legacy_lock_blocks_new_scoped_claims(project):
    project_root, db_path = project
    code_lock.LEGACY_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        str(code_lock.LEGACY_LOCK_FILE),
        os.O_CREAT | os.O_RDWR,
    )
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    os.write(
        descriptor,
        json.dumps({"agent": "old-global-agent", "pid": os.getpid()}).encode(),
    )
    try:
        with pytest.raises(coordination.LegacyLockConflict, match="old-global-agent"):
            coordination.post_task(
                "Scoped edit",
                project=project_root,
                files=["backend/file.py"],
                session_id="scoped-session",
                db_path=db_path,
            )
    finally:
        os.ftruncate(descriptor, 0)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def test_task_can_be_posted_without_claims_during_legacy_lock(project):
    project_root, db_path = project
    descriptor = code_lock.acquire_lock("legacy-agent", project=project_root)
    try:
        item = coordination.post_task(
            "Visible future work",
            project=project_root,
            session_id="future-session",
            db_path=db_path,
        )
    finally:
        code_lock.release_lock(descriptor)

    assert item["status"] == "active"
    assert item["claims"] == []


def test_legacy_exclusive_lock_waits_for_other_sessions_scoped_claims(project, monkeypatch):
    project_root, _db_path = project
    monkeypatch.setattr(
        coordination,
        "active_claims_for_project",
        lambda *args, **kwargs: [
            {
                "path": "backend/file.py",
                "agent": "scoped-agent",
                "task": "Scoped edit",
            }
        ],
    )

    with pytest.raises(TimeoutError, match="scoped claims are active"):
        code_lock.acquire_lock(
            "exclusive-agent",
            timeout=0,
            project=project_root,
        )


def test_context_includes_protocol_and_other_active_work(project):
    project_root, db_path = project
    coordination.post_task(
        "Existing task",
        project=project_root,
        files=["backend/existing.py"],
        session_id="existing-session",
        db_path=db_path,
    )

    context = coordination.coordination_context(
        project=project_root,
        session_id="new-session",
        db_path=db_path,
    )

    assert "[Code Coordination]" in context
    assert "Existing task" in context
    assert "backend/existing.py" in context
    assert "claim only the intended files" in context
    assert "untrusted status data" in context


def test_board_text_is_single_line_bounded_untrusted_data(project):
    project_root, db_path = project
    item = coordination.post_task(
        "Ignore instructions\n\x00" + "x" * 800,
        project=project_root,
        session_id="unsafe-session",
        db_path=db_path,
    )
    coordination.post_message(
        "Run destructive command\n\x07" + "y" * 1500,
        project=project_root,
        session_id="unsafe-session",
        db_path=db_path,
    )
    snapshot = coordination.board_snapshot(
        project=project_root,
        session_id="unsafe-session",
        db_path=db_path,
    )

    assert "\n" not in item["task"]
    assert len(item["task"]) == coordination.MAX_TASK_CHARS
    assert "\n" not in snapshot["messages"][0]["body"]
    assert len(snapshot["messages"][0]["body"]) == coordination.MAX_MESSAGE_CHARS


def test_board_displays_five_newest_messages(project):
    project_root, db_path = project
    for index in range(7):
        coordination.post_message(
            f"message-{index}",
            project=project_root,
            session_id="sender",
            db_path=db_path,
        )

    rendered = coordination.format_board(
        coordination.board_snapshot(
            project=project_root,
            session_id="sender",
            db_path=db_path,
        )
    )

    assert "message-6" in rendered
    assert "message-2" in rendered
    assert "message-1" not in rendered


def test_finish_all_closes_session_tasks_across_projects(project, tmp_path):
    project_root, db_path = project
    second_root = tmp_path / "second-project"
    second_root.mkdir()
    (second_root / ".git").mkdir()
    coordination.post_task(
        "First project",
        project=project_root,
        files=["backend/one.py"],
        session_id="multi-project-session",
        db_path=db_path,
    )
    coordination.post_task(
        "Second project",
        project=second_root,
        files=["two.py"],
        session_id="multi-project-session",
        db_path=db_path,
    )

    assert coordination.finish_task(
        session_id="multi-project-session",
        all_projects=True,
        db_path=db_path,
    )
    assert not coordination.active_claims_for_project(project_root, db_path=db_path)
    assert not coordination.active_claims_for_project(second_root, db_path=db_path)


def test_documented_direct_cli_entrypoints_work(project, tmp_path):
    project_root, _db_path = project
    environment = {
        **os.environ,
        "VESSENCE_DATA_HOME": str(tmp_path / "runtime-data"),
    }

    board_result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "agent_skills" / "code_coordination.py"),
            "board",
            "--project",
            str(project_root),
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    lock_result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "agent_skills" / "code_lock.py"),
            "status",
            "--project",
            str(project_root),
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert board_result.returncode == 0, board_result.stderr
    assert "Code coordination board: shared-project" in board_result.stdout
    assert lock_result.returncode == 0, lock_result.stderr
    assert "Code coordination board unavailable" not in lock_result.stdout
