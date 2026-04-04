import json

import pytest


def test_jane_stream_returns_error_event_when_backend_raises(monkeypatch):
    pytest.importorskip("itsdangerous")
    from fastapi import Request
    from jane_web import main as jane_main

    async def scenario():
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/jane/chat/stream",
            "headers": [],
        }
        request = Request(scope)
        body = jane_main.ChatMessage(message="hello", session_id="ignored")

        monkeypatch.setattr(jane_main, "get_or_bootstrap_session", lambda request: ("session-123", None))
        monkeypatch.setattr(jane_main, "get_session_user", lambda session_id: "user-1")

        async def failing_stream_message(user_id, session_id, message, file_context, platform=None, tts_enabled=False):
            raise RuntimeError("backend exploded")
            yield  # pragma: no cover

        monkeypatch.setattr(jane_main, "stream_message", failing_stream_message)

        response = await jane_main._handle_jane_chat_stream(body, request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        payload = json.loads("".join(chunks).strip())
        assert payload["type"] == "error"
        assert "backend exploded" in payload["data"]

    import asyncio

    asyncio.run(scenario())
