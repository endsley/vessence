from agent_skills import nightly_self_improve
from agent_skills.nightly_log_reader import (
    marker_window_for_run,
    read_job_log,
    read_text,
    timestamp_window_for_run,
)


def test_nightly_self_improve_uses_log_reader_helpers():
    assert nightly_self_improve._read_text is read_text
    assert nightly_self_improve._read_job_log is read_job_log


def test_read_text_returns_empty_for_missing_file_and_tails_existing_text(tmp_path):
    assert read_text(tmp_path / "missing.log") == ""

    path = tmp_path / "job.log"
    path.write_text("abcdef", encoding="utf-8")

    assert read_text(path) == "abcdef"
    assert read_text(path, tail_chars=3) == "def"


def test_timestamp_window_for_run_preserves_existing_windowing_behavior():
    text = (
        "2026-07-02 00:59:59 previous run\n"
        "2026-07-02 01:00:00 current start\n"
        "line without timestamp\n"
        "2026-07-02 01:00:10 current end allowance\n"
        "2026-07-02 01:00:11 next run\n"
    )

    assert timestamp_window_for_run(
        text,
        "2026-07-02T01:00:00",
        5,
        tail_chars=1000,
    ) == (
        "2026-07-02 01:00:00 current start\n"
        "line without timestamp\n"
        "2026-07-02 01:00:10 current end allowance\n"
    )


def test_marker_window_for_run_uses_exact_or_seconds_precision_marker():
    text = (
        "===== Run 2026-07-02T00:00:00 =====\nold\n\n"
        "===== Run 2026-07-02T01:00:00 =====\ncurrent\n\n"
        "===== Run 2026-07-02T02:00:00 =====\nnext\n"
    )

    assert marker_window_for_run(text, "2026-07-02T01:00:00.123") == (
        "===== Run 2026-07-02T01:00:00 =====\ncurrent"
    )


def test_read_job_log_falls_back_to_marker_then_tail(tmp_path):
    path = tmp_path / "job.log"
    path.write_text(
        "prefix\n"
        "===== Run 2026-07-02T01:00:00 =====\n"
        "current body\n\n"
        "===== Run 2026-07-02T02:00:00 =====\n"
        "next body\n",
        encoding="utf-8",
    )

    result = {
        "log": str(path),
        "started_iso": "2026-07-02T01:00:00.999",
        "elapsed_s": 1,
    }

    assert read_job_log(result) == (
        "===== Run 2026-07-02T01:00:00 =====\ncurrent body"
    )
    assert read_job_log({"log": str(path)}, tail_chars=10) == "next body\n"
