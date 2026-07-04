import datetime

from memory.v1.memory_text import (
    dedupe_fact_lines,
    extract_content_key,
    fmt_memory,
    is_expired,
    is_none_content,
    is_too_old,
    parse_memory_datetime,
    recency_label,
    recency_label_from_seconds,
)


def test_parse_memory_datetime_normalizes_iso_values_to_utc():
    assert parse_memory_datetime("2026-07-03T12:34:56Z") == datetime.datetime(
        2026, 7, 3, 12, 34, 56, tzinfo=datetime.timezone.utc
    )
    assert parse_memory_datetime("2026-07-03T12:34:56").tzinfo == datetime.timezone.utc
    assert parse_memory_datetime("") is None
    assert parse_memory_datetime("not a timestamp") is None


def test_is_expired_handles_numeric_and_iso_values():
    now = datetime.datetime.now(datetime.timezone.utc)

    assert is_expired({"expires_at": now.timestamp() - 10})
    assert not is_expired({"expires_at": now.timestamp() + 10})
    assert is_expired({"expires_at": (now - datetime.timedelta(seconds=10)).isoformat()})
    assert not is_expired({"expires_at": (now + datetime.timedelta(seconds=10)).isoformat()})
    assert not is_expired({"expires_at": "not a timestamp"})


def test_is_too_old_and_recency_label():
    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
    recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)

    assert is_too_old({"timestamp": old.isoformat()}, max_days=3)
    assert not is_too_old({"created_at": recent.isoformat()}, max_days=3)
    assert recency_label(recent.isoformat()).endswith("m ago")
    assert recency_label("Unknown Time") == "unknown age"


def test_recency_label_from_seconds_preserves_age_buckets():
    assert recency_label_from_seconds(-1) == "just now"
    assert recency_label_from_seconds(59) == "0m ago"
    assert recency_label_from_seconds(60) == "1m ago"
    assert recency_label_from_seconds(3599) == "59m ago"
    assert recency_label_from_seconds(3600) == "1h ago"
    assert recency_label_from_seconds(86399) == "23h ago"
    assert recency_label_from_seconds(86400) == "1d ago"


def test_none_content_and_formatting():
    assert is_none_content("None")
    assert is_none_content("")
    assert not is_none_content("real memory")

    formatted = fmt_memory(
        "Remember this",
        {"topic": "Project", "distance": 0.12345, "timestamp": "bad"},
    )
    assert formatted == "[unknown age] (Project) (Dist: 0.1235): Remember this"


def test_extract_content_key_and_dedupe_fact_lines():
    line1 = "[1d ago] (alpha) (Dist: 0.1): Same memory"
    line2 = "[2d ago] (beta) (Dist: 0.9): Same memory"
    line3 = "[3d ago] (beta): Other memory"

    assert extract_content_key(line1) == "same memory"
    assert dedupe_fact_lines([line1, line2, line3]) == [line1, line3]

    global_seen = {"same memory"}
    assert dedupe_fact_lines([line1, line3], global_seen) == [line3]
    assert "other memory" in global_seen
