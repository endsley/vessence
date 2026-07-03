from context_builder.v1 import context_builder
from context_builder.v1.tool_protocols import (
    CLASSIFICATION_TO_INTENT,
    PHONE_TOOLS_PROTOCOL,
    TOOL_CTX_CALL,
    TOOL_CTX_READ_EMAIL,
    TOOL_CTX_READ_MESSAGES,
    TOOL_CTX_SMS,
)


def test_context_builder_reexports_tool_protocol_assets():
    assert context_builder.PHONE_TOOLS_PROTOCOL is PHONE_TOOLS_PROTOCOL
    assert context_builder.TOOL_CTX_SMS is TOOL_CTX_SMS
    assert context_builder.TOOL_CTX_CALL is TOOL_CTX_CALL
    assert context_builder.TOOL_CTX_READ_MESSAGES is TOOL_CTX_READ_MESSAGES
    assert context_builder.TOOL_CTX_READ_EMAIL is TOOL_CTX_READ_EMAIL
    assert context_builder.CLASSIFICATION_TO_INTENT is CLASSIFICATION_TO_INTENT


def test_classification_to_intent_preserves_tool_mode_contexts():
    assert CLASSIFICATION_TO_INTENT["self_handle"] == ("greeting", None)
    assert CLASSIFICATION_TO_INTENT["read_messages"] == ("data_mode", TOOL_CTX_READ_MESSAGES)
    assert CLASSIFICATION_TO_INTENT["read_email"] == ("data_mode", TOOL_CTX_READ_EMAIL)
    assert CLASSIFICATION_TO_INTENT["sync_messages"] == ("data_mode", None)
    assert CLASSIFICATION_TO_INTENT["music_play"] == ("data_mode", None)
    assert CLASSIFICATION_TO_INTENT["delegate_opus"] == (None, None)


def test_phone_tools_protocol_keeps_legacy_fallback_sections():
    assert "## Phone Tools (Android only)" in PHONE_TOOLS_PROTOCOL
    assert "contacts.sms_draft" in PHONE_TOOLS_PROTOCOL
    assert "messages.read_inbox" in PHONE_TOOLS_PROTOCOL
    assert "timer.set" in PHONE_TOOLS_PROTOCOL
