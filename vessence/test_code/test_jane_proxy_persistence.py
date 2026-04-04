import time

from jane_web import jane_proxy


def test_persist_turns_async_invalidates_memory_cache():
    calls = []

    class StubConversationManager:
        def add_messages(self, messages):
            calls.append(("add_messages", messages))

    original_invalidate = jane_proxy.invalidate_memory_summary_cache
    try:
        jane_proxy.invalidate_memory_summary_cache = lambda session_id: calls.append(("invalidate", session_id))
        jane_proxy._persist_turns_async(
            "session-123",
            StubConversationManager(),
            {"role": "user", "content": "Maya is my new contact."},
            {"role": "assistant", "content": "Noted."},
            "Maya is my new contact.",
            "Noted.",
        )
        deadline = time.time() + 2
        while time.time() < deadline and len(calls) < 2:
            time.sleep(0.01)
    finally:
        jane_proxy.invalidate_memory_summary_cache = original_invalidate

    assert calls[0][0] == "add_messages"
    assert ("invalidate", "session-123") in calls


def test_persist_turns_async_survives_writeback_failure():
    calls = []

    class FailingConversationManager:
        def add_messages(self, messages):
            raise RuntimeError("db locked")

    original_log_stage = jane_proxy._log_stage
    original_update = jane_proxy.update_session_summary_async
    try:
        jane_proxy._log_stage = lambda session_id, stage, start_ts, **extra: calls.append((stage, extra))
        jane_proxy.update_session_summary_async = lambda session_id, user_message, assistant_message: calls.append(
            ("summary_dispatch", {"session_id": session_id, "assistant_message": assistant_message})
        )
        jane_proxy._persist_turns_async(
            "session-123",
            FailingConversationManager(),
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            "hello",
            "hi",
        )
        deadline = time.time() + 2
        while time.time() < deadline and not any(stage == "summary_dispatch" for stage, _ in calls):
            time.sleep(0.01)
    finally:
        jane_proxy._log_stage = original_log_stage
        jane_proxy.update_session_summary_async = original_update

    assert any(stage == "short_term_writeback_async_error" for stage, _ in calls)
    assert any(stage == "summary_dispatch" for stage, _ in calls)


def test_get_session_prunes_idle_sessions():
    class StubConversationManager:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    stale_manager = StubConversationManager()
    fresh_manager = StubConversationManager()
    original_ttl = jane_proxy.SESSION_IDLE_TTL_SECONDS
    try:
        jane_proxy._sessions.clear()
        jane_proxy.SESSION_IDLE_TTL_SECONDS = 60
        now = time.time()
        jane_proxy._sessions["stale-session"] = jane_proxy.JaneSessionState(
            conv_manager=stale_manager,
            last_accessed_at=now - 120,
        )
        jane_proxy._sessions["fresh-session"] = jane_proxy.JaneSessionState(
            conv_manager=fresh_manager,
            last_accessed_at=now,
        )

        jane_proxy._prune_stale_sessions(now)

        assert "stale-session" not in jane_proxy._sessions
        assert stale_manager.closed is True
        assert "fresh-session" in jane_proxy._sessions
        assert fresh_manager.closed is False
    finally:
        jane_proxy.SESSION_IDLE_TTL_SECONDS = original_ttl
        jane_proxy._sessions.clear()
