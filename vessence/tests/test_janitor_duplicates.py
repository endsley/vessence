import datetime as dt

from memory.v1.janitor_duplicates import (
    duplicate_deletion_groups,
    duplicate_row_timestamp,
    normalise_duplicate_doc,
    parse_stored_utc,
)


def row(row_id: str, doc: str, topic: str = "topic", subtopic: str = "", **meta):
    return {
        "id": row_id,
        "doc": doc,
        "meta": {"topic": topic, "subtopic": subtopic, **meta},
    }


def test_parse_stored_utc_handles_naive_z_and_offset_timestamps():
    assert parse_stored_utc("2026-07-02T12:00:00") == dt.datetime(2026, 7, 2, 12, 0, 0)
    assert parse_stored_utc("2026-07-02T12:00:00Z") == dt.datetime(2026, 7, 2, 12, 0, 0)
    assert parse_stored_utc("2026-07-02T08:00:00-04:00") == dt.datetime(2026, 7, 2, 12, 0, 0)
    assert parse_stored_utc("bad") is None
    assert parse_stored_utc(None) is None


def test_normalise_duplicate_doc_collapses_spacing_and_case():
    assert normalise_duplicate_doc(" Same\n  Memory  ") == "same memory"


def test_duplicate_row_timestamp_uses_first_available_timestamp_key():
    item = row(
        "a",
        "same durable memory text",
        updated_at="2026-07-02T12:00:00",
        timestamp="2026-07-03T12:00:00",
    )

    assert duplicate_row_timestamp(item) == dt.datetime(2026, 7, 2, 12, 0, 0)
    assert duplicate_row_timestamp(row("b", "same durable memory text")) == dt.datetime.min


def test_duplicate_deletion_groups_keep_newest_then_highest_id():
    old = row("a", "Same durable memory text that is long enough", updated_at="2026-07-01T12:00:00")
    newest = row("b", " same durable   memory text that is long enough ", updated_at="2026-07-02T12:00:00")
    different_subtopic = row("c", "Same durable memory text that is long enough", subtopic="other")
    tie_loser = row("d", "Another duplicated durable memory text", updated_at="2026-07-01T12:00:00")
    tie_winner = row("e", "Another duplicated durable memory text", updated_at="2026-07-01T12:00:00")
    too_short = row("f", "short")
    too_short_duplicate = row("g", "short")

    groups = duplicate_deletion_groups([
        old,
        newest,
        different_subtopic,
        tie_loser,
        tie_winner,
        too_short,
        too_short_duplicate,
    ])

    assert [[item["id"] for item in group] for group in groups] == [["a"], ["d"]]
