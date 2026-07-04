import json

from jane_web.broadcast import (
    BroadcastEvent,
    broadcast_summary_prompt,
    haiku_summary_log_entry,
    truncate_summary_log_lines,
)


def test_broadcast_summary_prompt_preserves_limits_and_instruction_shape():
    prompt = broadcast_summary_prompt("u" * 220, "r" * 1600)

    assert "Write ONE short sentence" in prompt
    assert f"User asked: {'u' * 200}\n" in prompt
    assert "Partial response so far (1600 chars):" in prompt
    assert f"{'r' * 1500}\n\nWrite ONE sentence" in prompt
    assert "u" * 201 not in prompt
    assert "r" * 1501 not in prompt


def test_haiku_summary_log_entry_preserves_json_shape_and_truncation():
    entry = json.loads(
        haiku_summary_log_entry(
            "u" * 180,
            "partial response",
            "Summarizing work.",
            timestamp="2026-07-04T12:00:00+00:00",
        )
    )

    assert entry == {
        "timestamp": "2026-07-04T12:00:00+00:00",
        "model": "haiku",
        "source": "broadcast",
        "user_msg": "u" * 150,
        "partial_len": len("partial response"),
        "summary": "Summarizing work.",
    }


def test_truncate_summary_log_lines_keeps_tail_only():
    lines = [f"{index}\n" for index in range(5)]

    assert truncate_summary_log_lines(lines, keep=3) == ["2\n", "3\n", "4\n"]
    assert truncate_summary_log_lines(lines, keep=10) == lines


def test_broadcast_event_json_preserves_public_shape_and_session_truncation():
    payload = json.loads(
        BroadcastEvent(
            event_type="progress",
            data="Working",
            source_session="session-1234567890",
            source_platform="android",
            user_message="hello",
            timestamp=123.0,
        ).to_json()
    )

    assert payload == {
        "type": "progress",
        "data": "Working",
        "source_session": "session-1234",
        "source_platform": "android",
        "user_message": "hello",
        "ts": 123.0,
    }
