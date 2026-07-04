from types import SimpleNamespace

from jane_web.proxy_sessions import (
    StaleSessionExpiration,
    global_idle_blocks_prune,
    oldest_session_key,
    read_global_idle_ts,
    session_composite_key,
    split_session_composite_key,
    stale_session_expirations,
    stale_session_keys,
)


def test_session_composite_key_round_trip_and_malformed_split():
    assert session_composite_key("user", "session") == "user:session"
    assert split_session_composite_key("user:session") == ("user", "session")
    assert split_session_composite_key("malformed") == ("malformed", "")


def test_global_idle_blocks_prune_only_with_recent_activity():
    assert global_idle_blocks_prune(100.0, 80.0, 30.0)
    assert global_idle_blocks_prune(100.0, 70.0, 30.0)
    assert not global_idle_blocks_prune(100.0, 69.9, 30.0)
    assert not global_idle_blocks_prune(100.0, 0.0, 30.0)


def test_read_global_idle_ts_clamps_future_and_tolerates_missing_or_bad_files(tmp_path):
    path = tmp_path / "activity.json"
    path.write_text('{"last_active_ts": 120.0}', encoding="utf-8")

    assert read_global_idle_ts(path, now_ts=100.0) == 100.0

    path.write_text('{"last_active_ts": 80.0}', encoding="utf-8")
    assert read_global_idle_ts(path, now_ts=100.0) == 80.0

    path.write_text("{", encoding="utf-8")
    assert read_global_idle_ts(path, now_ts=100.0) == 0.0
    assert read_global_idle_ts(tmp_path / "missing.json", now_ts=100.0) == 0.0


def test_stale_session_keys_use_strict_ttl_boundary():
    sessions = {
        "u:a": SimpleNamespace(last_accessed_at=50.0),
        "u:b": SimpleNamespace(last_accessed_at=70.0),
        "u:c": SimpleNamespace(last_accessed_at=69.9),
    }

    assert stale_session_keys(sessions, now_ts=100.0, ttl_seconds=30.0) == ["u:a", "u:c"]


def test_stale_session_expirations_include_split_key_and_idle_seconds():
    sessions = {
        "u:a": SimpleNamespace(last_accessed_at=50.5),
        "malformed": SimpleNamespace(last_accessed_at=40.0),
        "u:fresh": SimpleNamespace(last_accessed_at=95.0),
    }

    assert stale_session_expirations(sessions, now_ts=100.0, ttl_seconds=30.0) == [
        StaleSessionExpiration("u:a", "u", "a", 49),
        StaleSessionExpiration("malformed", "malformed", "", 60),
    ]


def test_oldest_session_key_uses_last_accessed_at():
    sessions = {
        "u:new": SimpleNamespace(last_accessed_at=100.0),
        "u:old": SimpleNamespace(last_accessed_at=1.0),
    }

    assert oldest_session_key(sessions) == "u:old"
