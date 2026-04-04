import asyncio

from jane.persistent_gemini import GeminiPersistentSession, TurnInterruptedError


def test_run_turn_retries_once_after_transient_restart_before_output():
    async def scenario():
        session = GeminiPersistentSession("session-1", "/tmp")
        spawned = []
        calls = []

        async def fake_spawn_locked():
            spawned.append("spawn")

        async def fake_run_turn_once(prompt_text: str, on_delta=None, timeout_seconds: float = 180.0) -> str:
            calls.append(prompt_text)
            if len(calls) == 1:
                raise TurnInterruptedError("Gemini persistent session restarted", emitted_len=0)
            return "Recovered response"

        session._spawn_locked = fake_spawn_locked  # type: ignore[method-assign]
        session._run_turn_once = fake_run_turn_once  # type: ignore[method-assign]

        result = await session.run_turn("hello")

        assert result == "Recovered response"
        assert calls == ["hello", "hello"]
        assert spawned == ["spawn"]

    asyncio.run(scenario())


def test_run_turn_does_not_retry_after_partial_output():
    async def scenario():
        session = GeminiPersistentSession("session-1", "/tmp")
        spawned = []

        async def fake_spawn_locked():
            spawned.append("spawn")

        async def fake_run_turn_once(prompt_text: str, on_delta=None, timeout_seconds: float = 180.0) -> str:
            raise TurnInterruptedError("Persistent Gemini session stopped", emitted_len=12)

        session._spawn_locked = fake_spawn_locked  # type: ignore[method-assign]
        session._run_turn_once = fake_run_turn_once  # type: ignore[method-assign]

        try:
            await session.run_turn("hello")
        except RuntimeError as exc:
            assert "Persistent Gemini session stopped" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError")

        assert spawned == []

    asyncio.run(scenario())
