import datetime

from jane_web import turn_dedupe
from jane_web.turn_dedupe import DedupeRow, _age_seconds_since, _existing_row_blocks_begin


def test_age_seconds_since_preserves_sqlite_timestamp_parsing():
    assert _age_seconds_since(
        "2026-07-03 12:00:00",
        now=datetime.datetime(2026, 7, 3, 12, 0, 30),
    ) == 30
    assert _age_seconds_since(
        "2026-07-03T12:00:00",
        now=datetime.datetime(2026, 7, 3, 12, 1, 0),
    ) == 60


def test_dedupe_row_age_seconds_uses_naive_utc_helper(monkeypatch):
    monkeypatch.setattr(
        turn_dedupe,
        "_utcnow",
        lambda: datetime.datetime(2026, 7, 3, 12, 0, 45),
    )

    row = DedupeRow(
        turn_id="turn-1",
        session_id="session",
        status="pending",
        response_json=None,
        created_at="2026-07-03 12:00:00",
        completed_at=None,
    )

    assert row.age_seconds == 45


def test_dedupe_row_age_seconds_falls_back_to_zero_for_bad_timestamps():
    row = DedupeRow(
        turn_id="turn-1",
        session_id="session",
        status="pending",
        response_json=None,
        created_at="bad timestamp",
        completed_at=None,
    )

    assert row.age_seconds == 0.0


def test_existing_row_blocks_begin_for_pending_or_completed_rows_inside_ttl():
    now = datetime.datetime(2026, 7, 3, 12, 5, 0)

    assert _existing_row_blocks_begin(
        "pending",
        "2026-07-03 12:00:00",
        now=now,
        ttl_seconds=300,
    )
    assert _existing_row_blocks_begin(
        "completed",
        "2026-07-03 12:00:00",
        now=now,
        ttl_seconds=300,
    )


def test_existing_row_allows_begin_for_failed_or_aged_out_rows():
    now = datetime.datetime(2026, 7, 3, 12, 5, 1)

    assert not _existing_row_blocks_begin(
        "pending",
        "2026-07-03 12:00:00",
        now=now,
        ttl_seconds=300,
    )
    assert not _existing_row_blocks_begin(
        "failed",
        "2026-07-03 12:05:00",
        now=now,
        ttl_seconds=300,
    )


def test_existing_row_blocks_begin_for_bad_pending_timestamps():
    assert _existing_row_blocks_begin("pending", "bad timestamp", ttl_seconds=300)
