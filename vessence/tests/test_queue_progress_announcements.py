from agent_skills import job_queue_runner, prompt_queue_runner
from agent_skills.queue_progress_announcements import (
    append_queue_progress_announcement,
    queue_announcements_path,
    queue_progress_id,
    queue_progress_json_line,
    queue_progress_payload,
)


def test_queue_runners_use_shared_announcement_helpers():
    assert prompt_queue_runner._append_queue_progress_announcement is append_queue_progress_announcement
    assert prompt_queue_runner._queue_announcements_path is queue_announcements_path
    assert prompt_queue_runner._queue_progress_id is queue_progress_id
    assert prompt_queue_runner._queue_progress_json_line is queue_progress_json_line
    assert job_queue_runner._append_queue_progress_announcement is append_queue_progress_announcement
    assert job_queue_runner._queue_announcements_path is queue_announcements_path
    assert job_queue_runner._queue_progress_id is queue_progress_id
    assert job_queue_runner._queue_progress_json_line is queue_progress_json_line


def test_queue_announcements_path_preserves_existing_jsonl_location():
    assert queue_announcements_path("/data/vessence") == (
        "/data/vessence/data/jane_announcements.jsonl"
    )


def test_queue_progress_id_preserves_existing_prefix_timestamp_shape():
    assert queue_progress_id("queue", 123456) == "queue_123456"
    assert queue_progress_id("job", 123456) == "job_123456"


def test_queue_progress_payload_preserves_existing_keys_and_values():
    assert queue_progress_payload(
        "queue_1",
        "**Working on:** demo",
        False,
        "2026-07-02T12:34:56+00:00",
    ) == {
        "timestamp": "2026-07-02T12:34:56+00:00",
        "type": "queue_progress",
        "id": "queue_1",
        "message": "**Working on:** demo",
        "final": False,
    }


def test_queue_progress_json_line_preserves_json_dump_shape():
    assert queue_progress_json_line(
        "queue_1",
        "**Completed:** demo",
        True,
        "2026-07-02T12:34:56+00:00",
    ) == (
        '{"timestamp": "2026-07-02T12:34:56+00:00", '
        '"type": "queue_progress", '
        '"id": "queue_1", '
        '"message": "**Completed:** demo", '
        '"final": true}'
    )


def test_append_queue_progress_announcement_appends_jsonl_line(tmp_path):
    path = tmp_path / "announcements.jsonl"

    append_queue_progress_announcement(
        str(path),
        "job_1",
        "**Working on job:** demo",
        False,
        "2026-07-02T12:34:56+00:00",
    )
    append_queue_progress_announcement(
        str(path),
        "job_1",
        "**Completed job:** demo",
        True,
        "2026-07-02T12:35:56+00:00",
    )

    assert path.read_text() == (
        '{"timestamp": "2026-07-02T12:34:56+00:00", '
        '"type": "queue_progress", '
        '"id": "job_1", '
        '"message": "**Working on job:** demo", '
        '"final": false}\n'
        '{"timestamp": "2026-07-02T12:35:56+00:00", '
        '"type": "queue_progress", '
        '"id": "job_1", '
        '"message": "**Completed job:** demo", '
        '"final": true}\n'
    )
