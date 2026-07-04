from datetime import datetime

from jane_web.jane_v2.body_message_updates import append_body_message, prepend_body_message
from jane_web.conversation_keys import scoped_conversation_session_id
from jane_web.jane_v2 import pipeline
from jane_web.jane_v2.pipeline import (
    _canonical_session_id,
    _copy_body_with_appended_message,
    _copy_body_with_prepended_message,
    _stage3_pending_extras_from_text,
)


class CopyBody:
    def __init__(self, message):
        self.message = message

    def copy(self, update):
        clone = CopyBody(self.message)
        clone.message = update["message"]
        return clone


class MutableBody:
    def __init__(self, message):
        self.message = message


def test_copy_body_with_appended_message_uses_existing_body_when_extra_empty():
    body = MutableBody("hello")

    assert _copy_body_with_appended_message is append_body_message
    assert _copy_body_with_prepended_message is prepend_body_message
    assert pipeline._resolve_scoped_conversation_session_id is scoped_conversation_session_id
    assert _copy_body_with_appended_message(body, "") is body


def test_copy_body_with_appended_message_preserves_copy_fallback():
    body = CopyBody("hello")

    copied = _copy_body_with_appended_message(body, " world")

    assert copied is not body
    assert copied.message == "hello world"
    assert body.message == "hello"


def test_copy_body_with_appended_message_mutates_when_no_copy_api_exists():
    body = MutableBody("hello")

    copied = _copy_body_with_appended_message(body, " world")

    assert copied is body
    assert body.message == "hello world"


def test_copy_body_with_prepended_message_adds_separator_only_when_needed():
    body = MutableBody("body")

    copied = _copy_body_with_prepended_message(body, "prefix")

    assert copied.message == "prefix\n\nbody"


def test_copy_body_with_prepended_message_preserves_double_newline_suffix():
    body = MutableBody("body")

    copied = _copy_body_with_prepended_message(body, "prefix\n\n")

    assert copied.message == "prefix\n\nbody"


def test_canonical_session_id_scopes_body_session_before_cookie(monkeypatch):
    calls = []

    class Body:
        session_id = " body-session "

    monkeypatch.setattr(pipeline, "_cookie_session_id", lambda _request: "cookie-session")
    monkeypatch.setattr(pipeline, "_cookie_session_user", lambda _request: "user@example.com")

    def fake_scope(user_id, session_id):
        calls.append((user_id, session_id))
        return f"scoped:{session_id}"

    monkeypatch.setattr(pipeline, "_resolve_scoped_conversation_session_id", fake_scope)

    assert _canonical_session_id(Body(), object()) == "scoped:body-session"
    assert calls == [("user@example.com", "body-session")]


def test_canonical_session_id_uses_cookie_fallback_and_none_when_missing(monkeypatch):
    class Body:
        session_id = ""

    monkeypatch.setattr(pipeline, "_cookie_session_user", lambda _request: "user@example.com")
    monkeypatch.setattr(
        pipeline,
        "_resolve_scoped_conversation_session_id",
        lambda user_id, session_id: f"{user_id}:{session_id}",
    )

    monkeypatch.setattr(pipeline, "_cookie_session_id", lambda _request: "cookie-session")
    assert _canonical_session_id(Body(), object()) == "user@example.com:cookie-session"

    monkeypatch.setattr(pipeline, "_cookie_session_id", lambda _request: "")
    assert _canonical_session_id(Body(), object()) is None


def test_pending_action_expires_at_preserves_zulu_timestamp_shape(monkeypatch):
    monkeypatch.setattr(pipeline, "_utcnow", lambda: datetime(2026, 6, 30, 12, 0, 0, 123456))

    assert pipeline._pending_action_expires_at(5) == "2026-06-30T12:05:00Z"


def test_stage2_pending_for_dispatch_copies_pending_data_and_question() -> None:
    pending_data = {"awaiting": "category"}
    pending = {"question": "Which category?"}

    result = pipeline._stage2_pending_for_dispatch(pending, pending_data)

    assert result == {"awaiting": "category", "question": "Which category?"}
    assert result is not pending_data
    assert pending_data == {"awaiting": "category"}


def test_stage2_pending_for_dispatch_preserves_existing_question() -> None:
    result = pipeline._stage2_pending_for_dispatch(
        {"question": "Outer question?"},
        {"awaiting": "category", "question": "Inner question?"},
    )

    assert result["question"] == "Inner question?"
    assert pipeline._stage2_pending_for_dispatch({"question": "Outer?"}, "bad") == {
        "question": "Outer?"
    }


def test_stage3_followup_original_class_handles_top_level_nested_and_bad_data() -> None:
    assert pipeline._stage3_followup_original_class({"original_class": "weather"}) == "weather"
    assert pipeline._stage3_followup_original_class({
        "data": {"original_class": "send message"}
    }) == "send message"
    assert pipeline._stage3_followup_original_class({"data": "bad"}) == ""


def test_stage3_followup_state_preserves_pending_marker_and_original_class() -> None:
    state = pipeline._stage3_followup_state(
        {
            "type": "STAGE3_FOLLOWUP",
            "handler_class": "stage3",
            "awaiting": "confirm_restart",
            "data": {"original_class": "restart server"},
        },
        "confirm_restart",
    )

    assert state == {
        "cls": "stage3_followup",
        "conf": "High",
        "classification": "stage3_followup:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": True,
        "stage3_followup_topic": "confirm_restart",
        "resolve_pending_action": {
            "type": "STAGE3_FOLLOWUP",
            "handler_class": "stage3",
            "status": "resolved",
            "resolution": "answered",
            "awaiting": "confirm_restart",
        },
        "stage3_followup_original_class": "restart server",
    }


def test_merge_resolved_pending_action_only_fills_missing_pending_action() -> None:
    resolved = {"type": "STAGE2_FOLLOWUP", "status": "resolved"}
    existing = {"pending_action": {"type": "NEW"}, "intent": "timer"}

    assert pipeline._merge_resolved_pending_action(None, None) is None
    assert pipeline._merge_resolved_pending_action(None, resolved) == {
        "pending_action": resolved
    }
    assert pipeline._merge_resolved_pending_action({"intent": "timer"}, resolved) == {
        "intent": "timer",
        "pending_action": resolved,
    }
    assert pipeline._merge_resolved_pending_action(existing, resolved) is existing


def test_stage3_pending_extras_prefers_sms_draft_over_awaiting(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "_pending_action_expires_at", lambda minutes: f"expires:{minutes}")
    text = (
        'draft [[CLIENT_TOOL:contacts.sms_draft:{"draft_id":"d1","query":"Mia","body":"Hi"}]] '
        "[[AWAITING:confirm send]]"
    )

    cleaned_text, awaiting_topic, extras = _stage3_pending_extras_from_text(
        text,
        {"cls": "weather"},
        awaiting_expiry_minutes=2,
    )

    assert "[[AWAITING:" not in cleaned_text
    assert awaiting_topic == "confirm_send"
    assert extras == {
        "intent": "send message",
        "pending_action": {
            "type": "SEND_MESSAGE_DRAFT_OPEN",
            "handler_class": "send message",
            "status": "awaiting_user",
            "awaiting": "confirm_draft",
            "data": {
                "draft_id": "d1",
                "query": "Mia",
                "body": "Hi",
            },
            "expires_at": "expires:5",
        },
    }


def test_stage3_pending_extras_builds_awaiting_followup(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "_pending_action_expires_at", lambda minutes: f"expires:{minutes}")

    cleaned_text, awaiting_topic, extras = _stage3_pending_extras_from_text(
        "Need details [[AWAITING:real topic]]",
        {"cls": "weather"},
        awaiting_expiry_minutes=2,
    )

    assert cleaned_text == "Need details"
    assert awaiting_topic == "real_topic"
    assert extras == {
        "pending_action": {
            "type": "STAGE3_FOLLOWUP",
            "handler_class": "stage3",
            "status": "awaiting_user",
            "awaiting": "real_topic",
            "expires_at": "expires:2",
            "original_class": "weather",
        }
    }


def test_stage3_pending_extras_omits_synthetic_original_class(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "_pending_action_expires_at", lambda minutes: f"expires:{minutes}")

    _, _, extras = _stage3_pending_extras_from_text(
        "Need details [[AWAITING:topic]]",
        {"cls": "others"},
        awaiting_expiry_minutes=5,
    )

    assert extras["pending_action"] == {
        "type": "STAGE3_FOLLOWUP",
        "handler_class": "stage3",
        "status": "awaiting_user",
        "awaiting": "topic",
        "expires_at": "expires:5",
    }


def test_stage3_pending_extras_returns_none_without_marker_or_draft() -> None:
    assert _stage3_pending_extras_from_text(
        "plain answer",
        {"cls": "weather"},
        awaiting_expiry_minutes=5,
    ) == ("plain answer", None, None)
