import datetime as dt

from memory.v1.conversation_windows import (
    build_role_content_transcript,
    build_session_transcript,
    build_window_transcript,
    first_metadata_timestamp,
    group_ledger_turns,
    latest_metadata_timestamp,
    normalize_timestamp_for_sql,
    parse_ledger_ts,
    should_start_new_ledger_window,
    transcript_line,
)


def test_parse_ledger_ts_accepts_sqlite_and_iso_shapes():
    assert parse_ledger_ts("2026-07-02 12:34:56") == dt.datetime(2026, 7, 2, 12, 34, 56)
    assert parse_ledger_ts("2026-07-02T12:34:56.789+00:00") == dt.datetime(2026, 7, 2, 12, 34, 56)
    assert parse_ledger_ts("") is None
    assert parse_ledger_ts("bad") is None


def test_normalize_timestamp_for_sql_matches_seed_query_shape():
    assert normalize_timestamp_for_sql("2026-07-02T12:34:56.789+00:00") == "2026-07-02 12:34:56"


def test_first_metadata_timestamp_preserves_field_precedence():
    assert first_metadata_timestamp(None) is None
    assert first_metadata_timestamp({}) is None
    assert first_metadata_timestamp(
        {
            "updated_at": "2026-07-04T00:00:00",
            "created_at": "2026-07-03T00:00:00",
            "timestamp": "2026-07-02T00:00:00",
            "archived_at": "2026-07-01T00:00:00",
        }
    ) == "2026-07-01T00:00:00"


def test_latest_metadata_timestamp_uses_first_available_timestamp_key():
    assert latest_metadata_timestamp(
        [
            None,
            {"updated_at": "2026-07-01T00:00:00"},
            {"archived_at": "2026-07-02T00:00:00", "updated_at": "2026-07-03T00:00:00"},
        ]
    ) == "2026-07-02T00:00:00"
    assert latest_metadata_timestamp([]) is None


def test_should_start_new_ledger_window_preserves_gap_and_size_policy():
    prev = dt.datetime(2026, 7, 2, 10, 0, 0)
    same_window = dt.datetime(2026, 7, 2, 10, 10, 0)
    next_window = dt.datetime(2026, 7, 2, 11, 0, 0)
    gap = dt.timedelta(minutes=30)

    assert not should_start_new_ledger_window(prev, next_window, 0, idle_gap=gap, max_turns=2)
    assert not should_start_new_ledger_window(prev, same_window, 1, idle_gap=gap, max_turns=2)
    assert should_start_new_ledger_window(prev, next_window, 1, idle_gap=gap, max_turns=2)
    assert should_start_new_ledger_window(prev, same_window, 2, idle_gap=gap, max_turns=2)
    assert not should_start_new_ledger_window(None, next_window, 1, idle_gap=gap, max_turns=2)
    assert not should_start_new_ledger_window(prev, None, 1, idle_gap=gap, max_turns=2)


def test_group_ledger_turns_splits_on_idle_gap_and_max_turns():
    rows = [
        (1, "user", "a", "2026-07-02 10:00:00"),
        (2, "assistant", "b", "2026-07-02 10:05:00"),
        (3, "user", "c", "2026-07-02 11:00:00"),
        (4, "assistant", "d", "2026-07-02 11:01:00"),
        (5, "user", "e", "2026-07-02 11:02:00"),
    ]

    windows = group_ledger_turns(rows, idle_gap_minutes=30, max_turns=2)

    assert [[turn[0] for turn in window] for window in windows] == [[1, 2], [3, 4], [5]]
    assert windows[0][0][3] == dt.datetime(2026, 7, 2, 10, 0, 0)


def test_build_window_transcript_cleans_metadata_and_skips_protocol_chatter():
    window = [
        (1, "user", "hello\n<class_protocol>x</class_protocol>", dt.datetime(2026, 7, 2, 10, 0, 0)),
        (2, "assistant", "I need clarification about [CURRENT CONVERSATION STATE]", dt.datetime(2026, 7, 2, 10, 1, 0)),
        (3, None, "kept", dt.datetime(2026, 7, 2, 10, 2, 0)),
    ]

    assert build_window_transcript(window) == "USER: hello\n\n: kept"


def test_transcript_line_and_session_transcript_share_cleaning_policy():
    assert transcript_line("user", "hello\n<class_protocol>x</class_protocol>") == "USER: hello"
    assert transcript_line("assistant", "I need clarification about [CURRENT CONVERSATION STATE]") is None
    assert transcript_line("assistant", "   ") is None

    assert build_role_content_transcript(
        [
            ("user", "first"),
            ("assistant", "[EXTRACTED PARAMS] hidden"),
            ("assistant", "second\nline"),
        ]
    ) == "USER: first\n\nASSISTANT: second line"

    assert build_session_transcript(
        [
            ("user", "first"),
            ("assistant", "[EXTRACTED PARAMS] hidden"),
            ("assistant", "second\nline"),
        ]
    ) == "USER: first\n\nASSISTANT: second line"
