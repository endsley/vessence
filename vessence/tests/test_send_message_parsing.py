import asyncio

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


def run(coro):
    return asyncio.run(coro)


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


def test_send_message_resume_predicate_accepts_handler_or_awaiting_data() -> None:
    assert handler._should_resume_send_message({"handler_class": "send message"})
    assert handler._should_resume_send_message({"data": {"awaiting": "revised_body"}})
    assert not handler._should_resume_send_message({"handler_class": "timer"})
    assert not handler._should_resume_send_message(None)


def test_send_message_resume_draft_fields_accept_nested_and_legacy_shapes() -> None:
    assert handler._resume_draft_fields({
        "data": {
            "awaiting": "send_confirmation",
            "draft": {"phone": "+15551234567", "display": "Mia", "body": "Running late"},
        }
    }) == ("send_confirmation", "+15551234567", "Mia", "Running late")

    assert handler._resume_draft_fields({"awaiting": "revised_body", "draft": {}}) == (
        "revised_body",
        "",
        "them",
        "",
    )


def test_send_message_confirmation_reply_preserves_yes_no_cancel_and_unknown_paths() -> None:
    yes = handler._handle_send_confirmation_reply("yes", "+15551234567", "Mia", "Running late")
    assert yes["conversation_end"] is True
    assert yes["structured"]["entities"]["message_body"] == "Running late"

    no = handler._handle_send_confirmation_reply("no", "+15551234567", "Mia", "Running late")
    assert no["text"] == "Please give me the updated message."
    assert no["structured"]["pending_action"]["awaiting"] == "revised_body"

    cancel = handler._handle_send_confirmation_reply("cancel", "+15551234567", "Mia", "Running late")
    assert cancel == {
        "text": "Ok.",
        "conversation_end": True,
        "structured": {"intent": "send message"},
    }

    assert handler._handle_send_confirmation_reply("maybe", "+15551234567", "Mia", "Running late") == {
        "abandon_pending": True,
        "force_stage3": True,
    }
    assert handler._handle_send_confirmation_reply("yes", "", "Mia", "Running late") == {
        "abandon_pending": True,
        "force_stage3": True,
    }


def test_send_message_revised_body_reply_preserves_one_word_body_and_abort_paths() -> None:
    response = handler._handle_revised_body_reply("yes", "+15551234567", "Mia")
    assert response["text"] == "Message to Mia: yes. Should I send it?"
    assert response["structured"]["pending_action"]["awaiting"] == "send_confirmation"

    assert handler._handle_revised_body_reply("   ", "+15551234567", "Mia") == {
        "abandon_pending": True,
        "force_stage3": True,
    }
    assert handler._handle_revised_body_reply("stop", "+15551234567", "Mia") == {
        "text": "Ok.",
        "conversation_end": True,
        "structured": {"intent": "send message"},
    }


def test_message_metadata_uses_classifier_params_without_llm() -> None:
    assert run(
        handler._message_metadata(
            "text Mia running late",
            "",
            {"recipient": " Mia ", "body": " Running late ", "confidence": 0.91},
        )
    ) == {
        "recipient": "Mia",
        "body": "Running late",
        "coherent": True,
        "confidence": 0.91,
    }
    assert run(handler._message_metadata("ask Mia when she is free", "", {"intent_kind": "ask"})) is None
    assert run(handler._message_metadata("text someone running late", "", {"body": "Running late"})) is None


def test_message_metadata_falls_back_to_llm_extract(monkeypatch) -> None:
    async def fake_extract(prompt, context):
        return {"recipient": prompt, "body": context, "coherent": True}

    monkeypatch.setattr(handler, "_extract_via_llm", fake_extract)

    assert run(handler._message_metadata("Mia", "Running late", None)) == {
        "recipient": "Mia",
        "body": "Running late",
        "coherent": True,
    }


def test_message_metadata_preserves_wrong_class_sentinel(monkeypatch) -> None:
    async def fake_extract(_prompt, _context):
        return WRONG_CLASS_SENTINEL

    monkeypatch.setattr(handler, "_extract_via_llm", fake_extract)

    assert run(handler._message_metadata("weather?", "", None)) is WRONG_CLASS_SENTINEL


class FakeAliasConn:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.existing


def test_auto_alias_contact_writes_only_new_contact_aliases() -> None:
    aliases = []
    conn = FakeAliasConn()

    wrote = handler._maybe_auto_alias_contact(
        "Lee",
        {"source": "contacts", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: (value or "").strip().lower(),
        add_alias_fn=lambda alias, phone, display_name: aliases.append((alias, phone, display_name)) or True,
        get_db_fn=lambda: conn,
    )

    assert wrote is True
    assert aliases == [("lee", "+1555", "Lee Chen")]
    assert conn.calls == [
        (
            "SELECT 1 FROM contact_aliases WHERE LOWER(alias) = ? LIMIT 1",
            ("lee",),
        )
    ]


def test_auto_alias_contact_skips_existing_aliases_and_non_contacts() -> None:
    assert not handler._maybe_auto_alias_contact(
        "Lee",
        {"source": "contacts", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: (value or "").strip().lower(),
        add_alias_fn=lambda *args, **kwargs: True,
        get_db_fn=lambda: FakeAliasConn(existing=(1,)),
    )
    assert not handler._maybe_auto_alias_contact(
        "Lee Chen",
        {"source": "contacts", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: (value or "").strip().lower(),
        add_alias_fn=lambda *args, **kwargs: True,
        get_db_fn=lambda: FakeAliasConn(),
    )
    assert not handler._maybe_auto_alias_contact(
        "Lee",
        {"source": "alias", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: (value or "").strip().lower(),
        add_alias_fn=lambda *args, **kwargs: True,
        get_db_fn=lambda: FakeAliasConn(),
    )


def test_resolve_message_recipient_returns_resolved_or_none() -> None:
    calls = []

    resolved = handler._resolve_message_recipient(
        {"recipient": "Mia"},
        lambda recipient: calls.append(recipient) or {
            "phone_number": "+1555",
            "display_name": "Mia",
        },
    )

    assert resolved == {"phone_number": "+1555", "display_name": "Mia"}
    assert calls == ["Mia"]
    assert handler._resolve_message_recipient({"recipient": "Unknown"}, lambda _recipient: None) is None


def test_auto_alias_resolved_recipient_reports_success_and_swallows_failure(monkeypatch) -> None:
    monkeypatch.setattr(handler, "_maybe_auto_alias_contact", lambda *args, **kwargs: True)

    assert handler._maybe_auto_alias_resolved_recipient(
        {"recipient": "Lee"},
        {"source": "contacts", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: value.lower(),
        add_alias_fn=lambda *args, **kwargs: True,
    )

    def fail_alias(*_args, **_kwargs):
        raise RuntimeError("db locked")

    monkeypatch.setattr(handler, "_maybe_auto_alias_contact", fail_alias)

    assert not handler._maybe_auto_alias_resolved_recipient(
        {"recipient": "Lee"},
        {"source": "contacts", "phone_number": "+1555", "display_name": "Lee Chen"},
        normalize_name_fn=lambda value: value.lower(),
        add_alias_fn=lambda *args, **kwargs: True,
    )


def test_resolved_message_response_escalates_without_body() -> None:
    assert handler._resolved_message_response(
        {"body": "(none)", "coherent": True},
        "+1555",
        "Mia",
    ) is None
    assert handler._resolved_message_response(
        {"body": " ", "coherent": True},
        "+1555",
        "Mia",
    ) is None


def test_resolved_message_response_confirms_incoherent_body() -> None:
    response = handler._resolved_message_response(
        {"body": "I will be at", "coherent": False},
        "+1555",
        "Mia",
    )

    assert response["text"] == "Message to Mia: I will be at. Should I send it?"
    assert response["structured"]["pending_action"]["awaiting"] == "send_confirmation"


def test_resolved_message_response_applies_confidence_floor() -> None:
    assert handler._resolved_message_response(
        {"body": "Running late", "coherent": True, "confidence": 0.79},
        "+1555",
        "Mia",
    ) is None

    response = handler._resolved_message_response(
        {"body": "Running late", "coherent": True, "confidence": 0.8},
        "+1555",
        "Mia",
    )

    assert response["conversation_end"] is True
    assert response["structured"]["entities"]["message_body"] == "Running late"


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
