import asyncio
import json

from jane_web.chat_stream_runner import normal_chat_stream_chunks, stream_identity


async def _collect(async_iterable):
    chunks = []
    async for chunk in async_iterable:
        chunks.append(chunk)
    return chunks


class FakeLogger:
    def __init__(self):
        self.debugs = []
        self.infos = []
        self.warnings = []
        self.exceptions = []

    def debug(self, *args):
        self.debugs.append(args)

    def info(self, *args):
        self.infos.append(args)

    def warning(self, *args):
        self.warnings.append(args)

    def exception(self, *args):
        self.exceptions.append(args)


def test_stream_identity_uses_authenticated_user_or_default_fallback():
    assert stream_identity(
        auth_session_id="auth-session",
        requested_conversation_session_id="body-session",
        get_session_user_fn=lambda session_id: f"user:{session_id}",
        default_user_id_fn=lambda: "default",
        scoped_session_id_fn=lambda user_id, session_id: f"{user_id}:{session_id}",
    ) == ("user:auth-session", "user:auth-session:body-session")

    assert stream_identity(
        auth_session_id="auth-session",
        requested_conversation_session_id="body-session",
        get_session_user_fn=lambda _session_id: None,
        default_user_id_fn=lambda: "default",
        scoped_session_id_fn=lambda user_id, session_id: f"{user_id}:{session_id}",
    ) == ("default", "default:body-session")


def test_normal_chat_stream_chunks_streams_and_finalizes_success():
    active_streams = {}
    calls = {}
    finalized = []

    async def stream_message(user_id, session_id, message, file_context, *, platform, tts_enabled):
        calls["stream"] = (user_id, session_id, message, file_context, platform, tts_enabled)
        yield '{"type": "delta", "data": "Hi"}\n'
        yield '{"type": "done", "data": "Hi"}\n'

    def finalize(turn_id, chunks, *, had_error):
        finalized.append((turn_id, list(chunks), had_error))

    chunks = asyncio.run(_collect(normal_chat_stream_chunks(
        active_streams=active_streams,
        stream_ip="198.51.100.5",
        auth_session_id="auth-session",
        body_session_id="body-session",
        requested_conversation_session_id="body-session",
        message="hello",
        file_context="file ctx",
        platform="web",
        tts_enabled=True,
        turn_id="turn-1",
        response_wait_seconds=1,
        stream_message_fn=stream_message,
        get_session_user_fn=lambda session_id: "user-1",
        default_user_id_fn=lambda: "default-user",
        scoped_session_id_fn=lambda user_id, session_id: f"{user_id}:{session_id}",
        session_log_id_fn=lambda session_id: session_id or "none",
        logger=FakeLogger(),
        finalize_turn_dedupe_fn=finalize,
    )))

    assert chunks == [
        '{"type": "delta", "data": "Hi"}\n',
        '{"type": "done", "data": "Hi"}\n',
    ]
    assert calls["stream"] == ("user-1", "user-1:body-session", "hello", "file ctx", "web", True)
    assert active_streams == {}
    assert finalized == [("turn-1", chunks, False)]


def test_normal_chat_stream_chunks_emits_error_and_marks_failed():
    active_streams = {}
    finalized = []
    logger = FakeLogger()

    async def stream_message(*args, **kwargs):
        raise RuntimeError("backend exploded")
        yield  # pragma: no cover

    def finalize(turn_id, chunks, *, had_error):
        finalized.append((turn_id, list(chunks), had_error))

    chunks = asyncio.run(_collect(normal_chat_stream_chunks(
        active_streams=active_streams,
        stream_ip="198.51.100.5",
        auth_session_id="auth-session",
        body_session_id="body-session",
        requested_conversation_session_id="body-session",
        message="hello",
        file_context=None,
        platform=None,
        tts_enabled=False,
        turn_id="turn-1",
        response_wait_seconds=1,
        stream_message_fn=stream_message,
        get_session_user_fn=lambda session_id: None,
        default_user_id_fn=lambda: "default-user",
        scoped_session_id_fn=lambda user_id, session_id: f"{user_id}:{session_id}",
        session_log_id_fn=lambda session_id: session_id or "none",
        logger=logger,
        finalize_turn_dedupe_fn=finalize,
    )))

    assert len(chunks) == 1
    payload = json.loads(chunks[0])
    assert payload["type"] == "error"
    assert "backend exploded" in payload["data"]
    assert active_streams == {}
    assert finalized == [("turn-1", [], True)]
    assert logger.exceptions
