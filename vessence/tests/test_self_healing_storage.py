import fcntl
import json
import time

import pytest

from agent_skills import self_healing_storage as storage


def test_atomic_private_json_write_creates_private_parseable_file(tmp_path):
    path = tmp_path / "nested" / "incident.json"

    storage.atomic_write_private_json(path, {"status": "captured", "attempts": 1})

    assert json.loads(path.read_text(encoding="utf-8")) == {"attempts": 1, "status": "captured"}
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_failed_atomic_replace_preserves_previous_incident_json(monkeypatch, tmp_path):
    path = tmp_path / "incident.json"
    storage.atomic_write_private_json(path, {"status": "captured", "attempts": 1})

    monkeypatch.setattr(storage.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        storage.atomic_write_private_json(path, {"status": "repair_retrying", "attempts": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"attempts": 1, "status": "captured"}


def test_private_json_update_merges_without_losing_existing_fields(tmp_path):
    path = tmp_path / "incident.json"
    storage.atomic_write_private_json(path, {"status": "captured", "id": "safe"})

    updated = storage.update_private_json(path, {"status": "repair_retrying", "repair_attempts": 1})

    assert updated == {"id": "safe", "status": "repair_retrying", "repair_attempts": 1}
    assert json.loads(path.read_text(encoding="utf-8")) == updated


def test_private_json_update_fails_promptly_without_changing_data_when_lock_is_held(tmp_path):
    path = tmp_path / "incident.json"
    storage.atomic_write_private_json(path, {"status": "captured", "id": "safe"})
    lock_path = path.with_suffix(path.suffix + ".lock")

    with lock_path.open("a+") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX)
        try:
            started = time.monotonic()
            with pytest.raises(storage.PrivateJsonLockUnavailable):
                storage.update_private_json(path, {"status": "repair_retrying"})
            assert time.monotonic() - started < 1
        finally:
            fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)

    assert json.loads(path.read_text(encoding="utf-8")) == {"id": "safe", "status": "captured"}
    assert lock_path.stat().st_mode & 0o777 == 0o600


def test_private_json_compare_and_update_is_atomic_and_does_not_write_on_mismatch(tmp_path):
    path = tmp_path / "incident.json"
    storage.atomic_write_private_json(path, {"status": "captured", "id": "safe"})

    changed, unchanged = storage.compare_and_update_private_json(
        path,
        lambda payload: payload.get("status") == "repair_retrying",
        {"status": "repair_finished"},
    )
    assert changed is False
    assert unchanged == {"id": "safe", "status": "captured"}
    assert json.loads(path.read_text(encoding="utf-8")) == unchanged

    changed, updated = storage.compare_and_update_private_json(
        path,
        lambda payload: payload.get("status") == "captured",
        {"status": "repair_retrying", "repair_attempts": 1},
    )
    assert changed is True
    assert updated == {"id": "safe", "status": "repair_retrying", "repair_attempts": 1}
    assert json.loads(path.read_text(encoding="utf-8")) == updated
