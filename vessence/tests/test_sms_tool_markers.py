from jane_web.jane_v2 import pending_sms, pipeline
from jane_web.jane_v2.classes.send_message import responses
from jane_web.jane_v2.sms_tool_markers import (
    SMS_DRAFT_MARKER_RE,
    sms_draft_cancel_marker,
    sms_draft_send_marker,
    sms_draft_update_marker,
    sms_send_direct_marker,
    stage3_sms_request_context,
)


def test_sms_marker_helpers_preserve_client_tool_shapes():
    assert sms_send_direct_marker("+15551234567", "Running late") == (
        '[[CLIENT_TOOL:contacts.sms_send_direct:{"phone_number": "+15551234567", '
        '"body": "Running late"}]]'
    )
    assert sms_draft_send_marker("draft-1") == (
        '[[CLIENT_TOOL:contacts.sms_send:{"draft_id": "draft-1"}]]'
    )
    assert sms_draft_cancel_marker("draft-1") == (
        '[[CLIENT_TOOL:contacts.sms_cancel:{"draft_id": "draft-1"}]]'
    )
    assert sms_draft_update_marker("draft-1", "Updated body") == (
        '[[CLIENT_TOOL:contacts.sms_draft_update:{"draft_id": "draft-1", '
        '"body": "Updated body"}]]'
    )


def test_sms_marker_helpers_are_used_by_v2_response_modules():
    assert pending_sms._SMS_DRAFT_MARKER_RE is SMS_DRAFT_MARKER_RE
    assert pending_sms._sms_send_direct_marker is sms_send_direct_marker
    assert responses._sms_send_direct_marker is sms_send_direct_marker


def test_sms_draft_marker_regex_preserves_action_and_json_groups():
    match = SMS_DRAFT_MARKER_RE.search(
        '[[CLIENT_TOOL:contacts.sms_draft_update:{"draft_id":"d1","body":"Hi"}]]'
    )

    assert match is not None
    assert match.group(1) == "sms_draft_update"
    assert match.group(2) == '{"draft_id":"d1","body":"Hi"}'


def test_stage3_sms_request_context_variants_are_centralized():
    non_streaming = stage3_sms_request_context()
    streaming = stage3_sms_request_context(streaming=True)

    assert pipeline._stage3_sms_request_context is stage3_sms_request_context
    assert "Use sms_send_direct:" in non_streaming
    assert "Resolve the recipient, confirm with user" in non_streaming
    assert "The user wants to send a TEXT MESSAGE (SMS)" in streaming
    assert "NEVER use contacts.call. NEVER use sms_draft for simple sends." in streaming
