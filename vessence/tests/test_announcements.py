import json
from datetime import datetime

from jane_web.announcements import AnnouncementsLog


def write_lines(path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_missing_announcements_log_returns_empty(tmp_path):
    log = AnnouncementsLog(tmp_path / "missing.jsonl")

    assert log.read(None) == []


def test_read_announcements_skips_invalid_json_and_filters_since(tmp_path):
    path = tmp_path / "announcements.jsonl"
    write_lines(
        path,
        [
            "",
            "{bad json",
            json.dumps({"id": "old", "created_at": "2026-01-01T09:00:00"}),
            json.dumps({"id": "equal", "created_at": "2026-01-01T10:00:00"}),
            json.dumps({"id": "new", "created_at": "2026-01-01T10:00:01"}),
            json.dumps({"id": "timestamp-new", "timestamp": "2026-01-01T11:00:00"}),
            json.dumps({"id": "bad-date", "created_at": "not-a-date"}),
            json.dumps({"id": "missing-date"}),
        ],
    )
    log = AnnouncementsLog(path)

    rows = log.read("2026-01-01T10:00:00")

    assert [row["id"] for row in rows] == ["new", "timestamp-new", "bad-date", "missing-date"]


def test_invalid_since_value_disables_date_filter(tmp_path):
    path = tmp_path / "announcements.jsonl"
    write_lines(
        path,
        [
            json.dumps({"id": "old", "created_at": "2026-01-01T09:00:00"}),
            json.dumps({"id": "new", "created_at": "2026-01-01T10:00:01"}),
        ],
    )
    log = AnnouncementsLog(path)

    assert [row["id"] for row in log.read("bad-date")] == ["old", "new"]


def test_announcement_since_filter_uses_created_at_then_timestamp_and_inclusive_cutoff():
    since_dt = datetime.fromisoformat("2026-01-01T10:00:00")

    assert not AnnouncementsLog._is_after_since({"created_at": "2026-01-01T10:00:00"}, since_dt)
    assert AnnouncementsLog._is_after_since({"timestamp": "2026-01-01T10:00:01"}, since_dt)
    assert AnnouncementsLog._is_after_since({"created_at": "not-a-date"}, since_dt)
    assert AnnouncementsLog._created_at_value({"timestamp": "fallback"}) == "fallback"


def test_announcement_since_filter_tolerates_mixed_timezone_awareness():
    since_dt = datetime.fromisoformat("2026-01-01T10:00:00+00:00")

    assert not AnnouncementsLog._is_after_since({"created_at": "2026-01-01T09:59:59"}, since_dt)
    assert AnnouncementsLog._is_after_since({"created_at": "2026-01-01T10:00:01"}, since_dt)


def test_large_log_is_truncated_to_recent_lines_before_reading(tmp_path):
    path = tmp_path / "announcements.jsonl"
    write_lines(
        path,
        [
            json.dumps({"id": "one"}),
            json.dumps({"id": "two"}),
            json.dumps({"id": "three"}),
            json.dumps({"id": "four"}),
        ],
    )
    log = AnnouncementsLog(path, max_bytes=1, keep_lines=2)

    rows = log.read(None)

    assert [row["id"] for row in rows] == ["three", "four"]
    assert [json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()] == ["three", "four"]


def test_read_announcements_collapses_historical_ra_reports_to_latest(tmp_path):
    path = tmp_path / "announcements.jsonl"
    write_lines(
        path,
        [
            json.dumps({"id": "regular-old", "type": "queue_progress", "created_at": "2026-07-01T09:00:00+00:00"}),
            json.dumps({
                "id": "ra_report_20260701",
                "type": "report_ready",
                "report_kind": "ra_research",
                "created_at": "2026-07-01T10:00:00+00:00",
            }),
            json.dumps({"id": "regular-new", "type": "queue_progress", "created_at": "2026-07-02T09:00:00+00:00"}),
            json.dumps({
                "id": "ra_report_20260702",
                "type": "report_ready",
                "report_kind": "ra_research",
                "created_at": "2026-07-02T10:00:00+00:00",
            }),
            json.dumps({
                "id": "ra_report_20260701_duplicate_late_row",
                "type": "report_ready",
                "report_kind": "ra_research",
                "created_at": "2026-07-01T10:00:00+00:00",
            }),
        ],
    )
    log = AnnouncementsLog(path)

    rows = log.read(None)

    assert [row["id"] for row in rows] == ["regular-old", "regular-new", "ra_report_20260702"]


def test_ra_report_collapse_runs_after_since_filter(tmp_path):
    path = tmp_path / "announcements.jsonl"
    write_lines(
        path,
        [
            json.dumps({
                "id": "ra_report_old",
                "type": "report_ready",
                "report_kind": "ra_research",
                "created_at": "2026-07-01T10:00:00+00:00",
            }),
            json.dumps({
                "id": "ra_report_new",
                "type": "report_ready",
                "report_kind": "ra_research",
                "created_at": "2026-07-03T10:00:00+00:00",
            }),
        ],
    )
    log = AnnouncementsLog(path)

    assert [row["id"] for row in log.read("2026-07-02T00:00:00+00:00")] == ["ra_report_new"]
    assert log.read("2026-07-04T00:00:00+00:00") == []
