import json

from jane_web.chat_stream_events import (
    OFFLOADED_TASK_MESSAGE,
    done_stream_chunk,
    error_stream_chunk,
    instant_command_stream_chunks,
    offloaded_task_stream_chunks,
    status_stream_chunk,
    stream_event_chunk,
)


def test_stream_event_chunk_preserves_ndjson_shape_and_extra_fields() -> None:
    chunk = stream_event_chunk("offloaded", "working", task_id="task-1")

    assert chunk.endswith("\n")
    assert json.loads(chunk) == {
        "type": "offloaded",
        "data": "working",
        "task_id": "task-1",
    }


def test_standard_stream_chunks_match_existing_event_shapes() -> None:
    assert done_stream_chunk("ok") == '{"type": "done", "data": "ok"}\n'
    assert status_stream_chunk("Loading") == '{"type": "status", "data": "Loading"}\n'
    assert error_stream_chunk("bad") == '{"type": "error", "data": "bad"}\n'


def test_instant_command_stream_chunks_emit_delta_then_done() -> None:
    assert instant_command_stream_chunks("Jobs: none") == [
        '{"type": "delta", "data": "Jobs: none"}\n',
        '{"type": "done", "data": "Jobs: none"}\n',
    ]


def test_offloaded_task_stream_chunks_preserve_user_message_and_task_id() -> None:
    chunks = offloaded_task_stream_chunks("task-123")

    assert [json.loads(chunk) for chunk in chunks] == [
        {"type": "offloaded", "data": OFFLOADED_TASK_MESSAGE, "task_id": "task-123"},
        {"type": "done", "data": OFFLOADED_TASK_MESSAGE},
    ]
