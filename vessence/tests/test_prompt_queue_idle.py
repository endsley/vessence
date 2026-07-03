from agent_skills import job_queue_runner, prompt_queue_runner
from agent_skills.prompt_queue_idle import (
    is_idle_from_timestamp,
    most_recent_activity_timestamp,
    most_recent_activity_timestamp_any,
    read_activity_timestamp,
    read_activity_timestamp_any,
)


class Logger:
    def __init__(self):
        self.messages = []

    def warning(self, message, *args):
        self.messages.append(message % args)


def test_prompt_queue_runner_uses_extracted_idle_helpers() -> None:
    assert prompt_queue_runner._read_activity_timestamp is read_activity_timestamp
    assert prompt_queue_runner._most_recent_activity_timestamp is most_recent_activity_timestamp
    assert prompt_queue_runner._is_idle_from_timestamp is is_idle_from_timestamp
    assert job_queue_runner._read_activity_timestamp_any is read_activity_timestamp_any
    assert job_queue_runner._most_recent_activity_timestamp_any is most_recent_activity_timestamp_any
    assert job_queue_runner._is_idle_from_timestamp is is_idle_from_timestamp


def test_read_activity_timestamp_handles_missing_bad_and_valid_files(tmp_path) -> None:
    logger = Logger()

    assert read_activity_timestamp(tmp_path / "missing.json", "last_message_ts", logger=logger) == 0.0

    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert read_activity_timestamp(bad, "last_message_ts", logger=logger) == 0.0
    assert logger.messages == ["bad.json read error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"]

    valid = tmp_path / "valid.json"
    valid.write_text('{"last_message_ts": 42.5}', encoding="utf-8")
    assert read_activity_timestamp(valid, "last_message_ts", logger=logger) == 42.5


def test_most_recent_activity_timestamp_and_idle_decision(tmp_path) -> None:
    first = tmp_path / "user.json"
    second = tmp_path / "idle.json"
    first.write_text('{"last_message_ts": 80}', encoding="utf-8")
    second.write_text('{"last_active_ts": 95}', encoding="utf-8")

    assert most_recent_activity_timestamp(
        [(first, "last_message_ts"), (second, "last_active_ts")]
    ) == 95.0
    assert is_idle_from_timestamp(100.0, 0.0, 30.0)
    assert not is_idle_from_timestamp(100.0, 95.0, 30.0)
    assert is_idle_from_timestamp(130.0, 100.0, 30.0)


def test_activity_timestamp_any_preserves_per_file_key_priority(tmp_path) -> None:
    first = tmp_path / "user.json"
    second = tmp_path / "idle.json"
    first.write_text('{"last_message_ts": 80, "last_active_ts": 95}', encoding="utf-8")
    second.write_text('{"last_active_ts": 70}', encoding="utf-8")

    assert read_activity_timestamp_any(
        first,
        ("last_message_ts", "last_active_ts"),
    ) == 80.0
    assert most_recent_activity_timestamp_any(
        [
            (first, ("last_message_ts", "last_active_ts")),
            (second, ("last_message_ts", "last_active_ts")),
        ]
    ) == 80.0
