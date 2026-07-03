from agent_skills import job_queue_runner, prompt_queue_runner
from agent_skills.queue_jane_api import (
    QueueStreamResult,
    parse_queue_stream_lines,
    queue_chat_payload,
    queue_chat_stream_url,
    queue_chat_sync_url,
    queue_http_error_result,
    queue_sync_response_result,
    run_queue_chat_request,
)


def test_queue_runners_use_shared_jane_api_helpers():
    assert prompt_queue_runner._queue_chat_payload is queue_chat_payload
    assert prompt_queue_runner._parse_queue_stream_lines is parse_queue_stream_lines
    assert prompt_queue_runner._run_queue_chat_request is run_queue_chat_request
    assert job_queue_runner._queue_chat_payload is queue_chat_payload
    assert job_queue_runner._parse_queue_stream_lines is parse_queue_stream_lines
    assert job_queue_runner._run_queue_chat_request is run_queue_chat_request


def test_queue_chat_payload_preserves_queue_platform_shape():
    assert queue_chat_payload("Do it", "prompt_queue_session") == {
        "message": "Do it",
        "session_id": "prompt_queue_session",
        "platform": "queue",
    }


def test_queue_chat_urls_preserve_existing_endpoint_paths():
    assert queue_chat_stream_url("http://localhost:8081") == (
        "http://localhost:8081/api/jane/chat/stream"
    )
    assert queue_chat_sync_url("http://localhost:8081") == (
        "http://localhost:8081/api/jane/chat"
    )


def test_parse_queue_stream_lines_accumulates_delta_events_and_ignores_noise():
    assert parse_queue_stream_lines(
        [
            "",
            "not json",
            '{"type": "delta", "data": "hel"}',
            '{"type": "delta", "data": "lo"}',
            '{"type": "done", "data": "ignored"}',
        ]
    ) == QueueStreamResult(text="hello", success=True)


def test_parse_queue_stream_lines_uses_done_data_when_no_delta_text():
    assert parse_queue_stream_lines(
        ['{"type": "done", "data": "final answer"}']
    ) == QueueStreamResult(text="final answer", success=True)


def test_parse_queue_stream_lines_preserves_empty_success_rule():
    assert parse_queue_stream_lines(
        ['{"type": "done", "data": "   "}']
    ) == QueueStreamResult(text="   ", success=False)


def test_parse_queue_stream_lines_preserves_error_result_shape():
    assert parse_queue_stream_lines(
        ['{"type": "error", "data": "bad"}']
    ) == QueueStreamResult(text="Error: bad", success=False, error="bad")


def test_queue_sync_and_http_error_results_preserve_runner_shapes():
    assert queue_sync_response_result({"text": "done"}) == QueueStreamResult(
        text="done",
        success=True,
        source="sync",
    )
    assert queue_sync_response_result({}) == QueueStreamResult(
        text="",
        success=False,
        source="sync",
    )
    assert queue_http_error_result(503) == QueueStreamResult(
        text="Error: HTTP 503",
        success=False,
        error="HTTP 503",
        source="sync",
    )


class _FakeResponse:
    def __init__(self, status_code=200, *, lines=None, payload=None, ok=None):
        self.status_code = status_code
        self._lines = lines or []
        self._payload = payload or {}
        self.ok = status_code < 400 if ok is None else ok

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def json(self):
        return self._payload


def test_run_queue_chat_request_handles_stream_success_and_error():
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(lines=['{"type": "done", "data": "streamed"}'])

    assert run_queue_chat_request(
        "http://jane",
        "Do it",
        "queue_session",
        post=post,
    ) == QueueStreamResult(text="streamed", success=True)
    assert calls == [
        (
            "http://jane/api/jane/chat/stream",
            {
                "json": queue_chat_payload("Do it", "queue_session"),
                "stream": True,
                "timeout": (10, None),
            },
        )
    ]

    def error_post(url, **kwargs):
        return _FakeResponse(lines=['{"type": "error", "data": "bad"}'])

    assert run_queue_chat_request("http://jane", "Do it", "queue_session", post=error_post) == (
        QueueStreamResult(text="Error: bad", success=False, error="bad")
    )


def test_run_queue_chat_request_handles_sync_fallback_success_and_failure():
    calls = []
    responses = [
        _FakeResponse(status_code=401),
        _FakeResponse(status_code=200, payload={"text": "sync answer"}),
    ]

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    assert run_queue_chat_request("http://jane", "Do it", "queue_session", post=post) == (
        QueueStreamResult(text="sync answer", success=True, source="sync")
    )
    assert calls == [
        (
            "http://jane/api/jane/chat/stream",
            {
                "json": queue_chat_payload("Do it", "queue_session"),
                "stream": True,
                "timeout": (10, None),
            },
        ),
        (
            "http://jane/api/jane/chat",
            {
                "json": queue_chat_payload("Do it", "queue_session"),
                "timeout": (10, 600),
            },
        ),
    ]

    responses = [
        _FakeResponse(status_code=401),
        _FakeResponse(status_code=500, ok=False),
    ]

    def failing_post(url, **kwargs):
        return responses.pop(0)

    assert run_queue_chat_request("http://jane", "Do it", "queue_session", post=failing_post) == (
        QueueStreamResult(text="Error: HTTP 500", success=False, error="HTTP 500", source="sync")
    )
