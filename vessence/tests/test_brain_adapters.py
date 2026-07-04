import subprocess

import pytest

from llm_brain.v1.brain_adapters import (
    BrainAdapter,
    BrainAdapterError,
    ExecutionProfile,
    _completed_subprocess_response,
    _resolve_idle_timeout,
    _resolve_provider_timeout,
    _resolve_wall_timeout,
    _timeout_error_message,
)


class FakeAdapter(BrainAdapter):
    label = "Fake"

    def build_command(self, system_prompt: str, transcript: str) -> list[str]:
        return ["fake"]


def test_timeout_error_message_preserves_idle_wall_and_generic_shapes():
    adapter = FakeAdapter(ExecutionProfile(max_wall_seconds=99))

    assert _timeout_error_message(
        adapter,
        subprocess.TimeoutExpired(["fake"], 5, output="idle for 5s"),
        idle_timeout=5,
    ) == "Fake CLI killed: no output for 5s (idle timeout)"
    assert _timeout_error_message(
        adapter,
        subprocess.TimeoutExpired(["fake"], 99, output="hit max wall-clock limit"),
        idle_timeout=5,
    ) == "Fake CLI killed: exceeded 99s wall-clock limit"
    assert _timeout_error_message(
        adapter,
        subprocess.TimeoutExpired(["fake"], 12, output=""),
        idle_timeout=5,
    ) == "Fake CLI timed out after 12s"


def test_completed_subprocess_response_parses_successful_stdout():
    adapter = FakeAdapter(ExecutionProfile())

    assert _completed_subprocess_response(adapter, ["  answer\n"], [], 0) == "answer"


def test_completed_subprocess_response_reports_nonzero_exit_with_stderr_first():
    adapter = FakeAdapter(ExecutionProfile())

    with pytest.raises(BrainAdapterError) as exc:
        _completed_subprocess_response(adapter, ["stdout"], ["stderr"], 2)

    assert str(exc.value) == "Fake CLI failed (exit code 2): stderr"


def test_completed_subprocess_response_reports_empty_output_with_stderr_hint():
    adapter = FakeAdapter(ExecutionProfile())

    with pytest.raises(BrainAdapterError) as exc:
        _completed_subprocess_response(adapter, ["   "], ["nothing here"], 0)

    assert str(exc.value) == (
        "Fake returned an empty response (exit code 0, stderr: nothing here)"
    )


def test_resolve_provider_timeout_preserves_specific_generic_and_default_order(monkeypatch):
    monkeypatch.setenv("JANE_TEST_TIMEOUT_CLAUDE", "11")
    monkeypatch.setenv("JANE_TEST_TIMEOUT", "22")

    assert _resolve_provider_timeout(
        "claude",
        base_key="JANE_TEST_TIMEOUT",
        defaults={"claude": 33},
        default=44,
    ) == 11
    assert _resolve_provider_timeout(
        "gemini",
        base_key="JANE_TEST_TIMEOUT",
        defaults={"gemini": 33},
        default=44,
    ) == 22

    monkeypatch.delenv("JANE_TEST_TIMEOUT")
    assert _resolve_provider_timeout(
        "gemini",
        base_key="JANE_TEST_TIMEOUT",
        defaults={"gemini": 33},
        default=44,
    ) == 33
    assert _resolve_provider_timeout(
        "unknown",
        base_key="JANE_TEST_TIMEOUT",
        defaults={"gemini": 33},
        default=44,
    ) == 44


def test_idle_and_wall_timeout_helpers_preserve_distinct_unknown_defaults(monkeypatch):
    monkeypatch.delenv("JANE_IDLE_TIMEOUT_UNKNOWN", raising=False)
    monkeypatch.delenv("JANE_IDLE_TIMEOUT", raising=False)
    monkeypatch.delenv("JANE_WALL_TIMEOUT_UNKNOWN", raising=False)
    monkeypatch.delenv("JANE_WALL_TIMEOUT", raising=False)

    assert _resolve_idle_timeout("unknown") == 120
    assert _resolve_wall_timeout("unknown") == 1800
