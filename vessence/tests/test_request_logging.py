from jane_web.request_logging import is_polling_path, request_error_context, should_touch_idle_state


def test_is_polling_path_matches_middleware_exemptions():
    assert is_polling_path("/api/jane/announcements")
    assert is_polling_path("/health")
    assert is_polling_path("/api/files/changes")
    assert is_polling_path("/api/jane/live")
    assert not is_polling_path("/api/jane/chat")


def test_should_touch_idle_state_for_non_polling_get_or_post_api_requests():
    assert should_touch_idle_state("/api/jane/chat", "GET")
    assert should_touch_idle_state("/api/jane/chat", "POST")
    assert not should_touch_idle_state("/api/jane/chat", "PUT")
    assert not should_touch_idle_state("/api/jane/announcements", "GET")
    assert not should_touch_idle_state("/chat", "GET")


def test_request_error_context_preserves_existing_keys():
    assert request_error_context(elapsed_ms=25, method="POST", path="/api/jane/chat") == {
        "elapsed_ms": 25,
        "method": "POST",
        "path": "/api/jane/chat",
    }
