from jane_web.jane_v2.pending_sms import (
    cancel_pending_sms_draft,
    extract_sms_draft_state,
    pending_consumed_marker,
    resolve_pending_sms_confirmation,
    resolve_pending_sms_draft_send,
)


def test_extract_sms_draft_state_tracks_latest_open_draft():
    text = (
        'draft [[CLIENT_TOOL:contacts.sms_draft:{"draft_id":"d1","query":"Mia","body":"Hi"}]] '
        'update [[CLIENT_TOOL:contacts.sms_draft_update:{"draft_id":"d1","body":"Hi there"}]]'
    )

    assert extract_sms_draft_state(text) == {
        "draft_id": "d1",
        "query": "Mia",
        "body": "Hi there",
    }


def test_extract_sms_draft_state_returns_none_after_send_or_cancel():
    sent = (
        'draft [[CLIENT_TOOL:contacts.sms_draft:{"draft_id":"d1","query":"Mia","body":"Hi"}]] '
        'send [[CLIENT_TOOL:contacts.sms_send:{"draft_id":"d1"}]]'
    )
    cancelled = (
        'draft [[CLIENT_TOOL:contacts.sms_draft:{"draft_id":"d2","query":"Mia","body":"Hi"}]] '
        'cancel [[CLIENT_TOOL:contacts.sms_cancel:{"draft_id":"d2"}]]'
    )

    assert extract_sms_draft_state(sent) is None
    assert extract_sms_draft_state(cancelled) is None


def test_pending_consumed_marker_includes_nested_awaiting():
    marker = pending_consumed_marker(
        {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": "todo list",
            "data": {"awaiting": "category"},
        }
    )

    assert marker == {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo list",
        "status": "resolved",
        "resolution": "answered",
        "awaiting": "category",
    }


def test_resolve_pending_sms_confirmation_builds_direct_send_marker():
    result = resolve_pending_sms_confirmation(
        {
            "data": {
                "phone_number": "+15551234567",
                "body": "Running late",
                "display_name": "Mia",
            }
        }
    )

    assert result["text"].startswith("Sending to Mia. [[CLIENT_TOOL:contacts.sms_send_direct:")
    assert result["structured"]["entities"] == {
        "recipient": "Mia",
        "message_body": "Running late",
        "phone_number": "+15551234567",
    }
    assert result["structured"]["pending_action"]["resolution"] == "confirmed"


def test_sms_draft_send_and_cancel_use_existing_draft_id():
    pending = {"data": {"draft_id": "draft-1", "query": "Mia", "body": "Hi"}}

    send = resolve_pending_sms_draft_send(pending)
    cancel = cancel_pending_sms_draft(pending)

    assert '[[CLIENT_TOOL:contacts.sms_send:{"draft_id": "draft-1"}]]' in send["text"]
    assert send["structured"]["pending_action"]["resolution"] == "sent"
    assert '[[CLIENT_TOOL:contacts.sms_cancel:{"draft_id": "draft-1"}]]' in cancel["text"]
    assert cancel["structured"]["pending_action"]["resolution"] == "cancelled"
