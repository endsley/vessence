import datetime as dt

from memory.v1.janitor_expiry import (
    expired_ids_from_metadata,
    is_expired_value,
    old_ids_from_metadata,
)


def test_is_expired_value_preserves_janitor_expiry_contract():
    now = dt.datetime(2026, 7, 2, 12, 0, 0).timestamp()

    assert not is_expired_value(None, now_ts=now)
    assert is_expired_value(now - 1, now_ts=now)
    assert not is_expired_value(now + 1, now_ts=now)
    assert is_expired_value("2026-07-02T11:59:59", now_ts=now)
    assert not is_expired_value("2026-07-02T12:00:01", now_ts=now)
    assert not is_expired_value("not a timestamp", now_ts=now)


def test_expired_ids_from_metadata_uses_expires_at_only():
    now = dt.datetime(2026, 7, 2, 12, 0, 0).timestamp()

    assert expired_ids_from_metadata(
        ["old", "future", "missing", "bad"],
        [
            {"expires_at": "2026-07-02T11:59:00"},
            {"expires_at": "2026-07-02T12:01:00"},
            {},
            {"expires_at": "bad"},
        ],
        now_ts=now,
    ) == ["old"]


def test_old_ids_from_metadata_uses_timestamp_and_ignores_bad_values():
    cutoff = dt.datetime(2026, 7, 2, 12, 0, 0)

    assert old_ids_from_metadata(
        ["old", "new", "created-only", "bad"],
        [
            {"timestamp": "2026-07-02T11:59:00"},
            {"timestamp": "2026-07-02T12:01:00"},
            {"created_at": "2026-07-01T00:00:00"},
            {"timestamp": "bad"},
        ],
        cutoff=cutoff,
    ) == ["old"]
