from jane_web.router_overrides import (
    _is_read_calendar_request,
    _is_read_email_request,
    _is_read_messages_request,
    _is_sync_messages_request,
    apply_router_keyword_overrides,
)


def test_router_keyword_matchers_preserve_intent_boundaries():
    assert _is_read_email_request("can you check my gmail inbox")
    assert not _is_read_email_request("email alex")
    assert _is_read_calendar_request("what's on my calendar today")
    assert _is_read_calendar_request("show my schedule")
    assert not _is_read_calendar_request("schedule a meeting with alex")
    assert _is_read_messages_request("show my texts")
    assert not _is_read_messages_request("send a text")
    assert _is_sync_messages_request("sync my sms messages")
    assert not _is_sync_messages_request("sync my calendar")


def test_router_keyword_overrides_read_email_requests():
    result = apply_router_keyword_overrides(
        "self_handle",
        "weather",
        "Can you check my Gmail inbox?",
    )

    assert result.classification == "read_email"
    assert result.response == "read_email"
    assert result.changes == (("self_handle", "read_email"),)


def test_router_keyword_overrides_calendar_read_requests_without_stealing_schedule_tasks():
    result = apply_router_keyword_overrides(
        "self_handle",
        "other",
        "What's on my calendar today?",
    )

    assert result.classification == "read_calendar"
    assert result.response == "today"
    assert result.changes == (("self_handle", "read_calendar"),)

    unchanged = apply_router_keyword_overrides(
        "self_handle",
        "other",
        "Schedule a meeting with Alex tomorrow",
    )
    assert unchanged.classification == "self_handle"
    assert unchanged.response == "other"
    assert unchanged.changes == ()


def test_router_keyword_overrides_text_read_requests():
    result = apply_router_keyword_overrides(
        "self_handle",
        "other",
        "Show my texts from today",
    )

    assert result.classification == "read_messages"
    assert result.response == "read_inbox"
    assert result.changes == (("self_handle", "read_messages"),)


def test_router_keyword_overrides_sync_requests_after_read_message_match():
    result = apply_router_keyword_overrides(
        "self_handle",
        "other",
        "Read and sync my SMS messages",
    )

    assert result.classification == "sync_messages"
    assert result.response == "sync"
    assert result.changes == (
        ("self_handle", "read_messages"),
        ("read_messages", "sync_messages"),
    )
