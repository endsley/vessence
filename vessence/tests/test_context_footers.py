from datetime import datetime

from jane_web.jane_v2.classes.context_footers import fetched_at_footer, utcnow_naive


def test_fetched_at_footer_preserves_timestamp_shape():
    footer = fetched_at_footer(
        "Use this context carefully.",
        now_fn=lambda: datetime(2026, 7, 3, 4, 5, 6, 789),
    )

    assert footer == "(Fetched at 2026-07-03T04:05:06.000789Z. Use this context carefully.)"


def test_utcnow_naive_returns_naive_datetime():
    assert utcnow_naive().tzinfo is None
