from jane_web.jane_v2.classes.send_message import handler
from jane_web.jane_v2.classes.send_message.extraction_prompt import (
    EXTRACT_PROMPT,
    build_extraction_prompt,
    extraction_context_block,
    extraction_request_payload,
)
from jane_web.jane_v2.classes.send_message.parsing import (
    WRONG_CLASS_SENTINEL,
    has_direct_send_confidence,
    is_coherent,
    parse_extraction,
    parse_params_metadata,
)
from jane_web.jane_v2.classes.send_message.responses import (
    build_confirmation_response,
    build_open_draft_cancel_response,
    build_open_draft_send_response,
    build_revision_request_response,
    build_send_marker,
    build_sent_response,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def test_handler_uses_extracted_send_message_helpers() -> None:
    assert handler._is_coherent is is_coherent
    assert handler._parse_extraction is parse_extraction
    assert handler._parse_params_metadata is parse_params_metadata
    assert handler._WRONG_CLASS_SENTINEL is WRONG_CLASS_SENTINEL
    assert handler._build_send_marker is build_send_marker
    assert handler._EXTRACT_PROMPT is EXTRACT_PROMPT
    assert handler._build_extraction_prompt is build_extraction_prompt
    assert handler._extraction_request_payload is extraction_request_payload
    assert handler._post_local_llm_response is post_local_llm_response


def test_extraction_prompt_includes_optional_context_and_strips_prompt() -> None:
    assert extraction_context_block(" prior turn ") == "Recent conversation:\nprior turn\n\n"
    assert extraction_context_block(" ") == ""

    prompt = build_extraction_prompt(" text mom hi ", "Jane: earlier")

    assert "Recent conversation:\nJane: earlier\n\nUser: text mom hi" in prompt
    assert "Output EXACTLY these 3 lines" in prompt


def test_extraction_request_payload_preserves_ollama_options() -> None:
    payload = extraction_request_payload(
        model="qwen",
        prompt="text mom hi",
        context="",
        num_ctx=4096,
        keep_alive="5m",
    )

    assert payload["model"] == "qwen"
    assert payload["prompt"].endswith("User: text mom hi")
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.0, "num_predict": 100, "num_ctx": 4096}
    assert payload["keep_alive"] == "5m"


def test_build_sent_response_preserves_direct_send_shape() -> None:
    response = build_sent_response("+15551234567", "Mia", "Running late")

    assert response["text"].startswith(
        'Done, message sent. [[CLIENT_TOOL:contacts.sms_send_direct:{"phone_number": "+15551234567", '
    )
    assert response["conversation_end"] is True
    assert response["structured"] == {
        "intent": "send message",
        "entities": {
            "recipient": "Mia",
            "phone_number": "+15551234567",
            "message_body": "Running late",
        },
        "safety": {"side_effectful": True, "requires_confirmation": False},
    }


def test_build_confirmation_and_revision_responses_preserve_pending_shapes() -> None:
    confirm = build_confirmation_response("+15551234567", "Mia", "Running late")
    pending = confirm["structured"]["pending_action"]

    assert confirm["text"] == "Message to Mia: Running late. Should I send it?"
    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "send message"
    assert pending["awaiting"] == "send_confirmation"
    assert pending["question"] == confirm["text"]
    assert pending["data"] == {
        "draft": {
            "phone": "+15551234567",
            "display": "Mia",
            "body": "Running late",
        },
        "awaiting": "send_confirmation",
    }

    revise = build_revision_request_response("+15551234567", "Mia")
    pending = revise["structured"]["pending_action"]
    assert revise["text"] == "Please give me the updated message."
    assert pending["awaiting"] == "revised_body"
    assert pending["data"] == {
        "draft": {"phone": "+15551234567", "display": "Mia"},
        "awaiting": "revised_body",
    }


def test_build_open_draft_send_and_cancel_responses_preserve_shapes() -> None:
    send = build_open_draft_send_response("draft-1", "Mia", "Running late")
    cancel = build_open_draft_cancel_response("draft-1", "Mia")

    assert '[[CLIENT_TOOL:contacts.sms_send:{"draft_id": "draft-1"}]]' in send["text"]
    assert send["structured"]["entities"] == {
        "recipient": "Mia",
        "message_body": "Running late",
        "draft_id": "draft-1",
    }
    assert send["structured"]["pending_action"] == {
        "type": "SEND_MESSAGE_DRAFT_OPEN",
        "status": "resolved",
        "resolution": "sent",
    }

    assert '[[CLIENT_TOOL:contacts.sms_cancel:{"draft_id": "draft-1"}]]' in cancel["text"]
    assert cancel["structured"]["pending_action"] == {
        "type": "SEND_MESSAGE_DRAFT_OPEN",
        "status": "resolved",
        "resolution": "cancelled",
    }


def test_direct_send_confidence_requires_numeric_floor() -> None:
    assert has_direct_send_confidence(0.80)
    assert has_direct_send_confidence(1)
    assert not has_direct_send_confidence(0.79)
    assert not has_direct_send_confidence(True)
    assert not has_direct_send_confidence("0.95")


def test_coherence_allows_missing_body_and_normal_messages() -> None:
    assert is_coherent("")
    assert is_coherent("(none)")
    assert is_coherent("I will be home soon")
    assert is_coherent("I talked to Alexander today")


def test_coherence_rejects_cutoffs_fillers_and_background_commands() -> None:
    assert not is_coherent("I will be at")
    assert not is_coherent("um I will be home soon")
    assert not is_coherent("hey siri set a timer")


def test_parse_extraction_parses_structured_llm_output() -> None:
    assert parse_extraction(
        "RECIPIENT: Kathia\nBODY: I will be home soon\nCOHERENT: yes"
    ) == {
        "recipient": "Kathia",
        "body": "I will be home soon",
        "coherent": True,
    }


def test_parse_extraction_combines_llm_and_rule_coherence() -> None:
    assert parse_extraction(
        "RECIPIENT: Kathia\nBODY: I will be at\nCOHERENT: yes"
    ) == {
        "recipient": "Kathia",
        "body": "I will be at",
        "coherent": False,
    }
    assert parse_extraction(
        "RECIPIENT: Kathia\nBODY: I will be home soon\nCOHERENT: no"
    ) == {
        "recipient": "Kathia",
        "body": "I will be home soon",
        "coherent": False,
    }


def test_parse_extraction_handles_wrong_class_missing_recipient_and_body() -> None:
    assert parse_extraction("WRONG_CLASS") is WRONG_CLASS_SENTINEL
    assert parse_extraction("BODY: Hello\nCOHERENT: yes") is None
    assert parse_extraction("RECIPIENT: Mom\nCOHERENT: yes") == {
        "recipient": "Mom",
        "body": "(none)",
        "coherent": True,
    }


def test_parse_params_metadata_preserves_classifier_param_path() -> None:
    status, metadata = parse_params_metadata({
        "recipient": " Kathia ",
        "body": " I will be at ",
        "intent_kind": "send",
        "confidence": 0.91,
    })

    assert status == "ok"
    assert metadata == {
        "recipient": "Kathia",
        "body": "I will be at",
        "coherent": False,
        "confidence": 0.91,
    }

    assert parse_params_metadata({"recipient": "Mom", "body": ""}) == (
        "ok",
        {
            "recipient": "Mom",
            "body": "(none)",
            "coherent": True,
            "confidence": None,
        },
    )
    assert parse_params_metadata({"recipient": "Mom", "intent_kind": "ask"}) == ("ask", None)
    assert parse_params_metadata({"body": "Running late"}) == ("missing_recipient", None)
