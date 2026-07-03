import json
from types import SimpleNamespace

from jane_web import proxy_logging
from jane_web.proxy_logging import ProxyRequestLogger


def logger_for(tmp_path, *, perf_counter=lambda: 2.0):
    return ProxyRequestLogger(
        tmp_path / "timing.log",
        tmp_path / "prompt.jsonl",
        perf_counter=perf_counter,
        strftime=lambda _fmt: "DATE",
    )


def test_truncate_log_if_needed_keeps_last_2000_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy_logging, "LOG_MAX_BYTES", 10)
    path = tmp_path / "large.log"
    path.write_text("\n".join(f"line-{i}" for i in range(2002)) + "\n", encoding="utf-8")
    request_logger = logger_for(tmp_path)

    request_logger.truncate_log_if_needed(path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2000
    assert lines[0] == "line-2"
    assert lines[-1] == "line-2001"


def test_log_stage_writes_duration_and_extra_fields(tmp_path):
    request_logger = logger_for(tmp_path, perf_counter=lambda: 3.25)

    request_logger.log_stage("session-1", "context_build", 2.0, chars=10, mode="sync")

    assert (tmp_path / "timing.log").read_text(encoding="utf-8") == (
        "DATE jane_request session=session-1 stage=context_build duration_ms=1250 chars=10 mode=sync\n"
    )


def test_log_start_writes_privacy_preserving_request_metadata(tmp_path):
    request_logger = logger_for(tmp_path)

    request_logger.log_start("session-1", "stream", "hello", 3, "Claude", "file")

    assert (tmp_path / "timing.log").read_text(encoding="utf-8") == (
        "DATE jane_request session=session-1 stage=start mode=stream "
        "message_chars=5 history_turns=3 brain=Claude file_context=True\n"
    )


def test_dump_prompt_writes_json_record(tmp_path):
    request_logger = logger_for(tmp_path)
    request_ctx = SimpleNamespace(
        retrieved_memory_summary="memory",
        system_prompt="system",
        transcript="transcript",
    )

    request_logger.dump_prompt(
        "session-1",
        "sync",
        "hello",
        "summary",
        request_ctx,
        True,
        "bootstrap café",
        "file",
    )

    record = json.loads((tmp_path / "prompt.jsonl").read_text(encoding="utf-8"))
    assert record["timestamp"] == "DATE"
    assert record["session_id"] == "session-1"
    assert record["message_chars"] == 5
    assert record["conversation_summary_chars"] == 7
    assert record["bootstrap_memory_summary"] == "bootstrap café"
    assert record["bootstrap_memory_summary_chars"] == len("bootstrap café")
    assert record["retrieved_memory_summary_chars"] == 6
    assert record["system_prompt_chars"] == 6
    assert record["transcript_chars"] == 10
    assert record["file_context"] == "file"
