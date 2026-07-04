import asyncio

from jane_web.jane_v2 import pending_sms
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


def test_pending_data_helper_accepts_only_dict_data():
    assert pending_sms._pending_data({"data": {"body": "hi"}}) == {"body": "hi"}
    assert pending_sms._pending_data({"data": "bad"}) == {}
    assert pending_sms._pending_data({}) == {}


def test_pending_consumed_marker_handles_malformed_data():
    marker = pending_consumed_marker(
        {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": "todo list",
            "data": "bad",
        }
    )

    assert marker == {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo list",
        "status": "resolved",
        "resolution": "answered",
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


def test_pending_sms_confirmation_handles_malformed_data():
    result = resolve_pending_sms_confirmation({"data": "bad"})
    cancelled = pending_sms.cancel_pending_sms_confirmation({"data": "bad"})

    assert "Sending to them." in result["text"]
    assert result["structured"]["entities"] == {
        "recipient": "them",
        "message_body": "",
        "phone_number": "",
    }
    assert cancelled["text"] == "Okay, not sending that to them."


def test_sms_draft_send_and_cancel_use_existing_draft_id():
    pending = {"data": {"draft_id": "draft-1", "query": "Mia", "body": "Hi"}}

    send = resolve_pending_sms_draft_send(pending)
    cancel = cancel_pending_sms_draft(pending)

    assert '[[CLIENT_TOOL:contacts.sms_send:{"draft_id": "draft-1"}]]' in send["text"]
    assert send["structured"]["pending_action"]["resolution"] == "sent"
    assert '[[CLIENT_TOOL:contacts.sms_cancel:{"draft_id": "draft-1"}]]' in cancel["text"]
    assert cancel["structured"]["pending_action"]["resolution"] == "cancelled"


def test_sms_draft_edit_prompt_contains_only_required_inputs():
    prompt = pending_sms._sms_draft_edit_prompt("Old body", "make it shorter")

    assert "CURRENT DRAFT BODY: Old body" in prompt
    assert "USER EDIT INSTRUCTION: make it shorter" in prompt
    assert prompt.endswith("NEW BODY:")


def test_clean_composed_sms_body_strips_quotes_and_label():
    assert pending_sms._clean_composed_sms_body(' "New body: Be there soon" ') == "Be there soon"
    assert pending_sms._clean_composed_sms_body("'Running late'") == "Running late"
    assert pending_sms._clean_composed_sms_body("   ") == ""


def test_sms_draft_update_response_preserves_pending_shape():
    result = pending_sms._sms_draft_update_response("draft-1", "Mia", "Running late")

    assert '[[CLIENT_TOOL:contacts.sms_draft_update:{"draft_id": "draft-1", "body": "Running late"}]]' in (
        result["text"]
    )
    assert result["structured"]["entities"] == {
        "recipient": "Mia",
        "message_body": "Running late",
        "draft_id": "draft-1",
    }
    assert result["structured"]["pending_action"] == {
        "type": "SEND_MESSAGE_DRAFT_OPEN",
        "status": "awaiting_user",
        "awaiting": "confirm_draft",
        "handler_class": "send message",
        "data": {
            "draft_id": "draft-1",
            "query": "Mia",
            "body": "Running late",
        },
    }


def test_sms_draft_edit_uses_shared_ollama_client(monkeypatch):
    captured = {}

    async def fake_post(prompt_text, payload_builder):
        captured["prompt"] = prompt_text
        captured["payload"] = payload_builder(
            prompt_text,
            model="qwen",
            num_ctx=4096,
            keep_alive="5m",
        )
        return "New body"

    monkeypatch.setattr(pending_sms, "_post_local_llm_response", fake_post)

    result = asyncio.run(
        pending_sms.resolve_pending_sms_draft_edit(
            {"data": {"draft_id": "draft-1", "query": "Mia", "body": "Old body"}},
            "make it shorter",
        )
    )

    assert captured["prompt"].endswith("NEW BODY:")
    assert captured["payload"]["prompt"].endswith("NEW BODY:")
    assert captured["payload"]["options"]["num_predict"] == 80
    assert captured["payload"]["keep_alive"] == "5m"
    assert '[[CLIENT_TOOL:contacts.sms_draft_update:{"draft_id": "draft-1", "body": "New body"}]]' in (
        result["text"]
    )
    assert result["structured"]["entities"]["message_body"] == "New body"
