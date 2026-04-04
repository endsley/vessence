from fastapi.testclient import TestClient
import asyncio
import types

from jane_web.main import app, require_auth
from jane_web import jane_proxy
from jane.context_builder import JaneRequestContext


async def _fake_stream_message(user_id: str, session_id: str, message: str, file_context: str = None):
    del user_id, session_id, message, file_context
    yield '{"type": "start", "data": null}\n'
    yield '{"type": "delta", "data": "Hello"}\n'
    yield '{"type": "delta", "data": " world"}\n'
    yield '{"type": "done", "data": "Hello world"}\n'


def test_jane_chat_stream_endpoint(monkeypatch):
    monkeypatch.setattr("jane_web.main.stream_message", _fake_stream_message)
    monkeypatch.setattr("jane_web.main.get_or_bootstrap_session", lambda request: ("test-session", None))
    monkeypatch.setattr("jane_web.main.get_session_user", lambda session_id: "test-user")

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/amber/chat/stream",
            json={"message": "hi", "session_id": "abc"},
        ) as response:
            body = "".join(
                chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                for chunk in response.iter_raw()
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert '"type": "delta"' in body
    assert '"data": "Hello world"' in body


def test_send_message_refreshes_memory_each_turn(monkeypatch):
    calls = []
    jane_proxy._sessions.clear()

    async def fake_build_context(message, history, **kwargs):
        calls.append(
            {
                "message": message,
                "history_len": len(history),
                "enable_memory_retrieval": kwargs.get("enable_memory_retrieval"),
                "memory_summary_fallback": kwargs.get("memory_summary_fallback"),
            }
        )
        return JaneRequestContext(
            system_prompt="system",
            transcript=f"User: {message}\nJane:",
            retrieved_memory_summary=f"memory for {message}",
        )

    async def fake_execute(*args, **kwargs):
        return "stub response"

    monkeypatch.setattr(jane_proxy, "build_jane_context_async", fake_build_context)
    monkeypatch.setattr(jane_proxy, "_execute_brain_sync", fake_execute)
    monkeypatch.setattr(jane_proxy, "_await_prewarm_if_running", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(jane_proxy, "_persist_turns_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_dump_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_log_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_log_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        jane_proxy,
        "get_brain_adapter",
        lambda *args, **kwargs: types.SimpleNamespace(label="stub"),
    )

    asyncio.run(jane_proxy.send_message("user", "session-1", "first turn"))
    asyncio.run(jane_proxy.send_message("user", "session-1", "second turn"))

    assert len(calls) == 2
    assert calls[0]["enable_memory_retrieval"] is True
    assert calls[0]["memory_summary_fallback"] == ""
    assert calls[1]["enable_memory_retrieval"] is True
    assert calls[1]["memory_summary_fallback"] == "memory for first turn"


def test_send_message_handles_context_build_failure(monkeypatch):
    jane_proxy._sessions.clear()

    async def fail_build_context(*args, **kwargs):
        raise RuntimeError("memory backend offline")

    monkeypatch.setattr(jane_proxy, "build_jane_context_async", fail_build_context)
    monkeypatch.setattr(jane_proxy, "_log_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_log_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        jane_proxy,
        "get_brain_adapter",
        lambda *args, **kwargs: types.SimpleNamespace(label="stub"),
    )

    result = asyncio.run(jane_proxy.send_message("user", "session-1", "first turn"))

    assert "could not prepare context" in result["text"].lower()
    assert "memory backend offline" in result["text"]


def test_stream_message_handles_context_build_failure(monkeypatch):
    jane_proxy._sessions.clear()

    async def fail_build_context(*args, **kwargs):
        raise RuntimeError("memory backend offline")

    async def collect_events():
        chunks = []
        async for chunk in jane_proxy.stream_message("user", "session-1", "first turn"):
            chunks.append(chunk)
        return chunks

    monkeypatch.setattr(jane_proxy, "build_jane_context_async", fail_build_context)
    monkeypatch.setattr(jane_proxy, "_log_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_log_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_await_prewarm_if_running", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(
        jane_proxy,
        "get_brain_adapter",
        lambda *args, **kwargs: types.SimpleNamespace(label="stub"),
    )

    chunks = asyncio.run(collect_events())
    body = "".join(chunks)

    assert '"type": "start"' in body
    assert '"type": "error"' in body
    assert "could not prepare context" in body.lower()


def test_stream_message_emits_error_when_brain_task_is_cancelled(monkeypatch):
    jane_proxy._sessions.clear()

    async def fake_build_context(*args, **kwargs):
        return JaneRequestContext(
            system_prompt="system",
            transcript="User: hi\nJane:",
            retrieved_memory_summary="",
        )

    async def cancelled_execute(*args, **kwargs):
        raise asyncio.CancelledError()

    async def collect_events():
        chunks = []
        async for chunk in jane_proxy.stream_message("user", "session-1", "first turn"):
            chunks.append(chunk)
        return chunks

    monkeypatch.setattr(jane_proxy, "build_jane_context_async", fake_build_context)
    monkeypatch.setattr(jane_proxy, "_execute_brain_stream", cancelled_execute)
    monkeypatch.setattr(jane_proxy, "_log_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_log_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_dump_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(jane_proxy, "_await_prewarm_if_running", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(
        jane_proxy,
        "get_brain_adapter",
        lambda *args, **kwargs: types.SimpleNamespace(label="stub"),
    )

    chunks = asyncio.run(collect_events())
    body = "".join(chunks)

    assert '"type": "error"' in body
    assert "interrupted before completion" in body.lower()


def test_get_execution_profile_uses_provider_defaults(monkeypatch):
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_CODEX", raising=False)
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_GEMINI", raising=False)

    assert jane_proxy._get_execution_profile("codex").timeout_seconds == 600
    assert jane_proxy._get_execution_profile("openai").timeout_seconds == 600
    assert jane_proxy._get_execution_profile("gemini").timeout_seconds == 180


def test_get_execution_profile_prefers_provider_override(monkeypatch):
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS", "240")
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS_CODEX", "900")

    assert jane_proxy._get_execution_profile("codex").timeout_seconds == 900
    assert jane_proxy._get_execution_profile("gemini").timeout_seconds == 240


def test_get_execution_profile_applies_codex_floor_over_shared_override(monkeypatch):
    monkeypatch.setenv("JANE_TIMEOUT_SECONDS", "180")
    monkeypatch.delenv("JANE_TIMEOUT_SECONDS_CODEX", raising=False)

    assert jane_proxy._get_execution_profile("codex").timeout_seconds == 600
    assert jane_proxy._get_execution_profile("openai").timeout_seconds == 600
    assert jane_proxy._get_execution_profile("gemini").timeout_seconds == 180
