import subprocess

import pytest

from agent_skills import claude_cli_llm


def test_completion_normalizes_timeout_without_echoing_prompt(monkeypatch):
    prompt = "private incident payload must not be echoed"

    monkeypatch.setattr(
        claude_cli_llm,
        "_build_command",
        lambda *args, **kwargs: ["codex", "exec", prompt],
    )

    signals = []

    class TimedOutProcess:
        pid = 4242
        returncode = None

        def __init__(self):
            self.calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(["codex", "exec", prompt], timeout=17)
            self.returncode = -15
            return "", ""

    popen_kwargs = []
    monkeypatch.setattr(
        claude_cli_llm.subprocess,
        "Popen",
        lambda *_args, **kwargs: popen_kwargs.append(kwargs) or TimedOutProcess(),
    )
    monkeypatch.setattr(claude_cli_llm.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    with pytest.raises(RuntimeError) as captured:
        claude_cli_llm.completion(prompt, timeout=17)

    assert str(captured.value) == "CLI (codex) timed out after 17s"
    assert prompt not in str(captured.value)
    assert popen_kwargs[0]["start_new_session"] is True
    assert signals == [(4242, claude_cli_llm.signal.SIGTERM)]


def test_completion_records_provider_lease_before_collecting_output(monkeypatch):
    started = []

    class CompletedProcess:
        pid = 5151
        returncode = 0

        def communicate(self, timeout=None):
            assert started == [5151]
            return "completed safely", ""

    monkeypatch.setattr(
        claude_cli_llm.subprocess,
        "Popen",
        lambda *_args, **_kwargs: CompletedProcess(),
    )

    assert claude_cli_llm.completion(
        "private prompt",
        cli="codex",
        on_process_started=lambda pid: started.append(pid) or True,
    ) == "completed safely"
    assert started == [5151]


def test_completion_stops_only_new_provider_group_when_lease_cannot_persist(monkeypatch):
    prompt = "private prompt must not appear in lease errors"
    signals = []

    class RejectedProcess:
        pid = 6161
        returncode = None

        def communicate(self, timeout=None):
            self.returncode = -15
            return "", ""

    monkeypatch.setattr(
        claude_cli_llm.subprocess,
        "Popen",
        lambda *_args, **_kwargs: RejectedProcess(),
    )
    monkeypatch.setattr(claude_cli_llm.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    with pytest.raises(claude_cli_llm.ProviderLeaseUnavailable) as captured:
        claude_cli_llm.completion(
            prompt,
            cli="codex",
            on_process_started=lambda _pid: False,
        )

    assert str(captured.value) == "critical repair provider lease unavailable"
    assert prompt not in str(captured.value)
    assert signals == [(6161, claude_cli_llm.signal.SIGTERM)]


def test_timeout_exception_reaches_provider_fallback_without_logging_prompt(monkeypatch, caplog):
    prompt = "do-not-log-this-provider-command"
    attempts = []

    def primary(*args, **kwargs):
        assert kwargs["use_fallback"] is False
        raise subprocess.TimeoutExpired(["codex", "exec", prompt], timeout=9)

    def fallback(*args, **kwargs):
        attempts.append(kwargs["cli"])
        return "fallback completed"

    monkeypatch.setattr(claude_cli_llm, "completion_orchestrator", primary)
    monkeypatch.setattr(claude_cli_llm, "completion", fallback)
    monkeypatch.setattr(claude_cli_llm, "_fallback_provider_sequence", lambda provider: ["claude"])
    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {"claude": {"cli": "claude", "smart": "smart", "cheap": "cheap"}},
    )

    assert claude_cli_llm.completion_with_fallback(prompt, tier="orchestrator", timeout=9) == "fallback completed"
    assert attempts == ["claude"]
    assert prompt not in caplog.text


def test_critical_repair_hands_zero_exit_codex_token_limit_to_claude(monkeypatch):
    prompt = "private repair prompt must not appear in provider failure state"
    calls = []

    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {
            "openai": {"cli": "codex", "smart": "gpt-test", "cheap": "gpt-cheap"},
            "claude": {"cli": "claude", "smart": "claude-test", "cheap": "claude-cheap"},
            "gemini": {"cli": "agy", "smart": "gemini-test", "cheap": "gemini-cheap"},
        },
    )

    def fake_completion(_prompt, **kwargs):
        calls.append(kwargs["cli"])
        if kwargs["cli"] == "codex":
            # Codex can return a limit notice as stdout with exit code zero.
            return "You've hit your usage limit. Please try again later."
        return "Claude completed the repair."

    monkeypatch.setattr(claude_cli_llm, "completion", fake_completion)

    assert claude_cli_llm.completion_for_critical_repair(prompt) == "Claude completed the repair."
    assert calls == ["codex", "claude"]


@pytest.mark.parametrize(
    "message",
    [
        "Maximum context window exceeded.",
        "Usage limit reached; please wait for reset.",
        "Too many requests. Retry later.",
    ],
)
def test_capacity_detector_recognizes_common_zero_exit_provider_wording(message):
    assert claude_cli_llm._looks_like_provider_capacity_response(message)


def test_critical_completion_hands_stderr_only_capacity_notice_to_claude(monkeypatch):
    """A zero exit with an innocuous stdout banner must not skip fallback."""
    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {
            "openai": {"cli": "codex", "smart": "gpt-test", "cheap": "gpt-cheap"},
            "claude": {"cli": "claude", "smart": "claude-test", "cheap": "claude-cheap"},
        },
    )
    calls = []

    def fake_completion(_prompt, **kwargs):
        calls.append((kwargs["cli"], kwargs.get("detect_capacity_response")))
        if kwargs["cli"] == "codex":
            # Simulate completion's opt-in combined stdout/stderr detection.
            raise claude_cli_llm.ProviderCapacityResponse("safe capacity classification")
        return "Claude completed the repair."

    monkeypatch.setattr(claude_cli_llm, "completion", fake_completion)

    assert claude_cli_llm.completion_for_critical_repair("private prompt") == "Claude completed the repair."
    assert calls == [("codex", True), ("claude", True)]


def test_critical_repair_result_records_actual_provider_without_private_output_in_metadata(monkeypatch):
    prompt = "private provider-rotation prompt"
    calls = []
    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {
            "openai": {"cli": "codex", "smart": "gpt-test", "cheap": "gpt-cheap"},
            "claude": {"cli": "claude", "smart": "claude-test", "cheap": "claude-cheap"},
        },
    )

    def fake_completion(_prompt, **kwargs):
        calls.append(kwargs["cli"])
        if kwargs["cli"] == "codex":
            raise RuntimeError("private codex failure")
        return "private Claude repair output"

    monkeypatch.setattr(claude_cli_llm, "completion", fake_completion)

    result = claude_cli_llm.completion_for_critical_repair_result(prompt)

    assert result.provider == "claude"
    assert result.output == "private Claude repair output"
    assert result.failed_attempts == ({"provider": "codex", "error_type": "RuntimeError"},)
    assert calls == ["codex", "claude"]


def test_critical_repair_forwards_provider_identity_to_lease_callback(monkeypatch):
    callbacks = []
    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {"openai": {"cli": "codex", "smart": "gpt-test", "cheap": "gpt-cheap"}},
    )

    def fake_completion(_prompt, **kwargs):
        assert kwargs["on_process_started"](7171) is True
        return "done"

    monkeypatch.setattr(claude_cli_llm, "completion", fake_completion)

    result = claude_cli_llm.completion_for_critical_repair_result(
        "private prompt",
        provider_order=("codex",),
        on_provider_started=lambda provider, pid: callbacks.append((provider, pid)) or True,
    )

    assert result.provider == "codex"
    assert callbacks == [("codex", 7171)]


def test_critical_repair_provider_exhaustion_is_structural_and_never_uses_gemini(monkeypatch):
    prompt = "do-not-persist-this-private-repair-prompt"
    calls = []

    monkeypatch.setattr(
        claude_cli_llm,
        "PROVIDER_MODELS",
        {
            "openai": {"cli": "codex", "smart": "gpt-test", "cheap": "gpt-cheap"},
            "claude": {"cli": "claude", "smart": "claude-test", "cheap": "claude-cheap"},
            "gemini": {"cli": "agy", "smart": "gemini-test", "cheap": "gemini-cheap"},
        },
    )

    def failed_completion(_prompt, **kwargs):
        calls.append(kwargs["cli"])
        raise RuntimeError("provider failure mentioning " + prompt)

    monkeypatch.setattr(claude_cli_llm, "completion", failed_completion)

    with pytest.raises(claude_cli_llm.RepairProvidersExhausted) as captured:
        claude_cli_llm.completion_for_critical_repair(prompt)

    assert calls == ["codex", "claude"]
    assert captured.value.attempts == (
        {"provider": "codex", "error_type": "RuntimeError"},
        {"provider": "claude", "error_type": "RuntimeError"},
    )
    assert prompt not in str(captured.value)
