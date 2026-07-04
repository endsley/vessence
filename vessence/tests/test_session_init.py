import asyncio
from types import SimpleNamespace

from jane_web.session_init import _session_init_prompt, session_init_stream_chunks


async def _collect(async_iterable):
    chunks = []
    async for chunk in async_iterable:
        chunks.append(chunk)
    return chunks


def test_session_init_prompt_preserves_system_prompt_and_greeting_constraint():
    prompt = _session_init_prompt("SYSTEM")

    assert prompt.startswith("SYSTEM\n\nThis is a session initialization.")
    assert "single short, warm greeting (1 sentence max)" in prompt
    assert prompt.endswith("Do not ask questions.")


def test_session_init_stream_chunks_builds_context_and_runs_init_turn():
    calls = {}

    async def build_context(prompt, history, **kwargs):
        calls["context"] = (prompt, history, kwargs)
        kwargs["on_status"]("Loaded memories")
        return SimpleNamespace(system_prompt="SYSTEM")

    class Manager:
        async def run_turn(self, user_id, session_id, prompt, **kwargs):
            calls["run_turn"] = (user_id, session_id, prompt, kwargs)
            return " Hello "

    chunks = asyncio.run(_collect(session_init_stream_chunks(
        manager=Manager(),
        build_context_async=build_context,
        get_execution_profile_fn=lambda brain: SimpleNamespace(timeout_seconds=12, mode="yolo"),
        brain_name="claude",
        user_id="user-1",
        session_id="session-1",
        init_status="Sending init prompt to Claude...",
        status_chunk_fn=lambda status: f"status:{status}",
        done_chunk_fn=lambda text: f"done:{text}",
        logger=SimpleNamespace(exception=lambda message: None),
    )))

    assert chunks == [
        "status:Loading personality and context...",
        "status:Loaded memories",
        "status:Sending init prompt to Claude...",
        "done:Hello",
    ]
    assert calls["context"] == (
        "Session initialization",
        [],
        {
            "session_id": "session-1",
            "platform": "web",
            "on_status": calls["context"][2]["on_status"],
            "user_id": "user-1",
        },
    )
    user_id, session_id, prompt, run_kwargs = calls["run_turn"]
    assert user_id == "user-1"
    assert session_id == "session-1"
    assert prompt.startswith("SYSTEM\n\nThis is a session initialization.")
    assert run_kwargs["timeout_seconds"] == 12
    assert run_kwargs["model"] is None
    assert run_kwargs["yolo"] is True


def test_session_init_stream_chunks_yields_fallback_on_error():
    logged = []

    async def build_context(*args, **kwargs):
        raise RuntimeError("context failed")

    chunks = asyncio.run(_collect(session_init_stream_chunks(
        manager=SimpleNamespace(),
        build_context_async=build_context,
        get_execution_profile_fn=lambda brain: SimpleNamespace(timeout_seconds=12, mode="normal"),
        brain_name="codex",
        user_id="user-1",
        session_id="session-1",
        init_status="Sending init prompt to Codex...",
        status_chunk_fn=lambda status: f"status:{status}",
        done_chunk_fn=lambda text: f"done:{text}",
        logger=SimpleNamespace(exception=lambda message: logged.append(message)),
    )))

    assert chunks == ["done:Hey! Ready when you are."]
    assert logged == ["Init session failed"]
