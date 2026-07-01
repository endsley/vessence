from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from jane_web.jane_v2 import pending_action_resolver as resolver


def test_expired_pending_accepts_z_and_offset_timestamps():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    with patch.object(resolver, "_utc_now", return_value=now):
        assert resolver._is_expired({
            "expires_at": "2026-06-30T11:59:00Z",
        })
        assert not resolver._is_expired({
            "expires_at": "2026-06-30T08:01:00-04:00",
        })


def test_expired_pending_treats_naive_timestamps_as_utc():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    with patch.object(resolver, "_utc_now", return_value=now):
        assert resolver._is_expired({
            "expires_at": "2026-06-30T11:59:59",
        })
        assert not resolver._is_expired({
            "expires_at": "2026-06-30T12:00:01",
        })


def test_expired_pending_malformed_timestamp_still_fails_open():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    with patch.object(resolver, "_utc_now", return_value=future):
        assert not resolver._is_expired({
            "expires_at": "not-a-timestamp",
        })
