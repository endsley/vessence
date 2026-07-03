import json

from agent_skills import transcript_quality_review
from agent_skills.transcript_review_sources import (
    load_android_events,
    load_pipeline_events,
    load_prompt_dump,
)


def test_load_prompt_dump_filters_date_and_skips_bad_json(tmp_path):
    path = tmp_path / "jane_prompt_dump.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({
                "timestamp": "2026-07-01T09:00:00Z",
                "session_id": "abcdef1234567890",
                "message": "hello",
                "mode": "voice",
            }),
            "{not json}",
            json.dumps({
                "timestamp": "2026-07-02T09:00:00Z",
                "session_id": "ignored",
                "message": "wrong day",
            }),
        ])
    )

    assert load_prompt_dump(path, "2026-07-01") == [
        {
            "time": "2026-07-01T09:00:00Z",
            "session": "abcdef123456",
            "user_msg": "hello",
            "mode": "voice",
        }
    ]
    assert load_prompt_dump(tmp_path / "missing.jsonl", "2026-07-01") == []


def test_load_pipeline_events_filters_relevant_lines_and_missing_file(tmp_path):
    path = tmp_path / "jane_web.log"
    path.write_text(
        "2026-07-01 stage1_classifier classified weather\n"
        "2026-07-01 irrelevant\n"
        "2026-07-02 stage1_classifier wrong day\n"
    )

    assert load_pipeline_events(path, "2026-07-01") == [
        "2026-07-01 stage1_classifier classified weather",
    ]
    assert load_pipeline_events(tmp_path / "missing.log", "2026-07-01") == []


def test_load_android_events_filters_categories_and_skips_bad_json(tmp_path):
    path = tmp_path / "android_diagnostics.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({
                "timestamp": "2026-07-01T09:00:00Z",
                "category": "voice_flow",
                "message": "handled",
                "path": "stage2",
            }),
            "{not json}",
            json.dumps({
                "timestamp": "2026-07-01T09:01:00Z",
                "category": "other",
                "message": "skip",
            }),
        ])
    )

    assert load_android_events(path, "2026-07-01") == [
        "2026-07-01T09:00:00Z [voice_flow] handled path=stage2",
    ]
    assert load_android_events(tmp_path / "missing.jsonl", "2026-07-01") == []


def test_transcript_quality_review_reexports_source_loaders():
    assert transcript_quality_review._load_prompt_dump_from_path is load_prompt_dump
    assert transcript_quality_review._load_pipeline_events_from_path is load_pipeline_events
    assert transcript_quality_review._load_android_events_from_path is load_android_events
