import asyncio
import sys
import time

import pytest

from llm_brain.v1.brain_adapters import BrainAdapter, BrainAdapterError, ExecutionProfile, build_execution_profile, resolve_timeout_seconds, _resolve_idle_timeout
from llm_brain.v1.persistent_gemini import GeminiPersistentSession


class SilentAdapter(BrainAdapter):
    name = "silent"
    label = "Silent"

    def build_command(self, system_prompt: str, transcript: str) -> list[str]:
        del system_prompt, transcript
        return [sys.executable, "-c", "import time; time.sleep(5)"]


def test_execute_stream_times_out_when_subprocess_emits_nothing():
    adapter = SilentAdapter(ExecutionProfile(timeout_seconds=1, idle_timeout_seconds=1, max_wall_seconds=10))
    started = time.monotonic()

    with pytest.raises(BrainAdapterError, match="idle timeout"):
        adapter.execute_stream("system", "transcript", lambda _delta: None)

    assert time.monotonic() - started < 3


def test_persistent_gemini_close_suppresses_reader_task_cancellation():
    async def run():
        session = GeminiPersistentSession(session_id="test", cwd=".")
        session.reader_task = asyncio.create_task(asyncio.sleep(60))
        await session._close_locked()
        assert session.reader_task is None

    asyncio.run(run())


def test_persistent_gemini_startup_exit_sets_failure():
    async def run():
        session = GeminiPersistentSession(session_id="test", cwd=".")
        session.process = type("Proc", (), {"returncode": 7})()
        session.master_fd = None
        session.startup_buffer = "fatal auth failure"
        session.ready_event.clear()

        reader = asyncio.create_task(session._read_loop())
        await asyncio.wait_for(session.ready_event.wait(), timeout=1)
        assert session.start_failure is not None
        assert "failed during startup" in str(session.start_failure)

        await reader

    asyncio.run(run())


def test_resolve_timeout_seconds_uses_provider_defaults(monkeypatch):
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_CODEX", raising=False)
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_OPENAI", raising=False)

    assert resolve_timeout_seconds("codex") == 600
    assert resolve_timeout_seconds("openai") == 600
    assert resolve_timeout_seconds("gemini") == 180


def test_resolve_timeout_seconds_applies_provider_floor(monkeypatch):
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS", "180")
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_CODEX", raising=False)

    assert resolve_timeout_seconds("codex") == 600
    assert resolve_timeout_seconds("openai") == 600
    assert resolve_timeout_seconds("gemini") == 180


def test_build_execution_profile_uses_provider_specific_override(monkeypatch):
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS", "240")
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS_CODEX", "900")
    monkeypatch.setenv("JANE_EXECUTION_MODE", "YOLO")

    profile = build_execution_profile("codex")

    assert profile.timeout_seconds == 900
    assert profile.mode == "yolo"
