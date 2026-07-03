import json

from jane_web import task_offloader
from jane_web.task_offloader_announcements import (
    QUEUE_PROGRESS_TYPE,
    append_task_progress_announcement,
    task_progress_json_line,
    task_progress_payload,
)


def test_task_offloader_uses_extracted_announcement_writer():
    assert task_offloader._append_task_progress_announcement is append_task_progress_announcement


def test_task_progress_payload_preserves_existing_non_final_shape():
    assert task_progress_payload(
        "bg_1",
        "⏳ Working",
        "2026-07-02T12:34:56+00:00",
    ) == {
        "id": "bg_1",
        "type": QUEUE_PROGRESS_TYPE,
        "message": "⏳ Working",
        "created_at": "2026-07-02T12:34:56+00:00",
    }


def test_task_progress_payload_adds_final_only_for_final_entries():
    assert task_progress_payload(
        "bg_1",
        "done",
        "2026-07-02T12:35:56+00:00",
        final=True,
    ) == {
        "id": "bg_1",
        "type": "queue_progress",
        "message": "done",
        "created_at": "2026-07-02T12:35:56+00:00",
        "final": True,
    }


def test_task_progress_json_line_preserves_unicode_output():
    assert task_progress_json_line(
        "bg_1",
        "⏳ Working",
        "2026-07-02T12:34:56+00:00",
    ) == (
        '{"id": "bg_1", '
        '"type": "queue_progress", '
        '"message": "⏳ Working", '
        '"created_at": "2026-07-02T12:34:56+00:00"}'
    )


def test_append_task_progress_announcement_creates_parent_and_appends(tmp_path):
    path = tmp_path / "nested" / "announcements.jsonl"

    append_task_progress_announcement(
        path,
        "bg_1",
        "working",
        "2026-07-02T12:34:56+00:00",
    )
    append_task_progress_announcement(
        path,
        "bg_1",
        "done",
        "2026-07-02T12:35:56+00:00",
        final=True,
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "id": "bg_1",
            "type": "queue_progress",
            "message": "working",
            "created_at": "2026-07-02T12:34:56+00:00",
        },
        {
            "id": "bg_1",
            "type": "queue_progress",
            "message": "done",
            "created_at": "2026-07-02T12:35:56+00:00",
            "final": True,
        },
    ]
