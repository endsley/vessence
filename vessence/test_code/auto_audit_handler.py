from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "send_message" / "handler.py"
)
SPEC_PATH = REPO_ROOT / "CLAUDE.md"

from agent_skills import sms_helpers
from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage1_classifier, stage2_dispatcher
from jane_web.jane_v2.classes.send_message import handler as send_handler
from jane_web.jane_v2.classes.send_message import metadata as send_metadata


DIRECT_SEND_RE = re.compile(
    r"\[\[CLIENT_TOOL:contacts\.sms_send_direct:(\{.*?\})\]\]"
)
ANY_SMS_TOOL_RE = re.compile(r"\[\[CLIENT_TOOL:contacts\.(sms_[a-z_]+):(\{.*?\})\]\]")

DOCUMENTED_NO_HANDLER_ESCALATES = {
    "delegate opus",
    "delete email",
    "end conversation",
    "others",
    "read email",
    "send email",
    "unclear",
}

DESTRUCTIVE_CLASS_NAMES = {
    "delete email",
    "delete messages",
    "end conversation",
    "send email",
    "send message",
}


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def sms_protocol_source() -> str:
    text = SPEC_PATH.read_text()
    start = text.index("## Text Message (SMS) Protocols")
    end = text.index("### Reading Messages", start)
    return text[start:end]


def _disable_open_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(send_handler, "_check_open_draft", lambda prompt: None)


def _block_llm_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(*_args: Any, **_kwargs: Any) -> dict | None:
        raise AssertionError("params path should not call the LLM extractor")

    monkeypatch.setattr(send_handler, "_extract_via_llm", forbidden)


def _install_recipient_resolution(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, dict[str, Any] | None],
) -> list[str]:
    calls: list[str] = []

    def resolve_recipient(name: str) -> dict[str, Any] | None:
        calls.append(name)
        return mapping.get(name)

    monkeypatch.setattr(sms_helpers, "resolve_recipient", resolve_recipient)
    monkeypatch.setattr(sms_helpers, "add_alias", lambda *_args, **_kwargs: True)
    return calls


def _result_text(result: dict | None) -> str:
    assert isinstance(result, dict)
    assert "text" in result
    assert isinstance(result["text"], str)
    return result["text"]


def _direct_send_payload(text: str) -> dict[str, Any]:
    match = DIRECT_SEND_RE.search(text)
    assert match, text
    return json.loads(match.group(1))


def _sms_tool(text: str) -> tuple[str, dict[str, Any]]:
    match = ANY_SMS_TOOL_RE.search(text)
    assert match, text
    return match.group(1), json.loads(match.group(2))


def _assert_no_client_tool(result: dict | None) -> None:
    if result is None:
        return
    assert isinstance(result, dict)
    assert "[[CLIENT_TOOL:" not in result.get("text", "")


def _send_confirmation_pending(
    *,
    phone: str = "+15551234567",
    display: str = "Kathia",
    body: str = "I love you",
) -> dict[str, Any]:
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "send message",
        "awaiting": "send_confirmation",
        "data": {
            "awaiting": "send_confirmation",
            "draft": {"phone": phone, "display": display, "body": body},
        },
        "question": f"Message to {display}: {body}. Should I send it?",
    }


def _revised_body_pending(
    *,
    phone: str = "+15551234567",
    display: str = "Kathia",
) -> dict[str, Any]:
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "send message",
        "awaiting": "revised_body",
        "data": {
            "awaiting": "revised_body",
            "draft": {"phone": phone, "display": display},
        },
        "question": "Please give me the updated message.",
    }


class _FakeCursor:
    def __init__(self, row: Any = None):
        self._row = row

    def fetchone(self) -> Any:
        return self._row


class _FakeConnection:
    def __init__(self, row: Any = None):
        self.row = row
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _FakeCursor:
        self.executed.append((sql, params))
        return _FakeCursor(self.row)


class TestDocumentedSmsProtocol:
    def test_claude_sms_protocol_documents_sms_not_calls(
        self, sms_protocol_source: str
    ) -> None:
        assert "ALWAYS SMS" in sms_protocol_source
        assert "NEVER use `contacts.call`" in sms_protocol_source
        assert "sms_send_direct" in sms_protocol_source
        assert "Rewrite perspective" in sms_protocol_source

    def test_module_docstring_documents_stage2_branches(self) -> None:
        doc = send_handler.__doc__ or ""

        assert "Fast path" in doc
        assert "Confirm-or-revise" in doc
        assert "Escalate" in doc
        assert "sms_send_direct" in doc
        assert "conversation_end=True" in doc
        assert "STAGE2_FOLLOWUP" in doc

    @pytest.mark.asyncio
    async def test_fast_path_resolved_coherent_body_sends_direct_and_ends(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        resolve_calls = _install_recipient_resolution(
            monkeypatch,
            {
                "wife": {
                    "phone_number": "+15551234567",
                    "display_name": "Kathia",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "tell my wife I love her",
            params={"recipient": "wife", "body": "I love you", "intent_kind": "send"},
        )

        text = _result_text(result)
        payload = _direct_send_payload(text)
        assert "message sent" in text.lower()
        assert payload == {"phone_number": "+15551234567", "body": "I love you"}
        assert result["conversation_end"] is True
        assert result["structured"]["intent"] == "send message"
        assert result["structured"]["entities"] == {
            "recipient": "Kathia",
            "phone_number": "+15551234567",
            "message_body": "I love you",
        }
        assert result["structured"]["safety"] == {
            "side_effectful": True,
            "requires_confirmation": False,
        }
        assert resolve_calls == ["wife"]

    @pytest.mark.asyncio
    async def test_params_intent_kind_ask_escalates_before_contact_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)

        def forbidden_lookup(name: str) -> None:
            raise AssertionError(f"ask intent must not resolve/send in Stage 2: {name}")

        monkeypatch.setattr(sms_helpers, "resolve_recipient", forbidden_lookup)

        result = await send_handler.handle(
            "ask Lee what time she is coming",
            params={
                "recipient": "Lee",
                "body": "What time are you coming?",
                "intent_kind": "ask",
            },
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_recipient_escalates_without_llm_or_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        monkeypatch.setattr(
            sms_helpers,
            "resolve_recipient",
            lambda name: (_ for _ in ()).throw(AssertionError(name)),
        )

        result = await send_handler.handle(
            "text somebody hi",
            params={"recipient": "", "body": "hi", "intent_kind": "send"},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_body_escalates_and_does_not_send(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom",
            params={"recipient": "mom", "body": "", "intent_kind": "send"},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_unresolved_recipient_escalates_without_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        resolve_calls = _install_recipient_resolution(monkeypatch, {"lee": None})

        result = await send_handler.handle(
            "text Lee I'm running late",
            params={"recipient": "lee", "body": "I'm running late", "intent_kind": "send"},
        )

        assert result is None
        assert resolve_calls == ["lee"]

    @pytest.mark.asyncio
    async def test_incoherent_body_asks_for_confirm_or_revise_not_direct_send(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom I will be at the",
            params={"recipient": "mom", "body": "I will be at the", "intent_kind": "send"},
        )

        text = _result_text(result)
        assert text == "Message to Mom: I will be at the. Should I send it?"
        assert "[[CLIENT_TOOL:" not in text
        pending = result["structured"]["pending_action"]
        assert pending["type"] == "STAGE2_FOLLOWUP"
        assert pending["handler_class"] == "send message"
        assert pending["awaiting"] == "send_confirmation"
        assert pending["data"]["draft"] == {
            "phone": "+15557654321",
            "display": "Mom",
            "body": "I will be at the",
        }

    @pytest.mark.asyncio
    async def test_wrong_class_llm_sentinel_propagates_for_dispatcher_self_correction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)

        async def wrong_class(_prompt: str, _context: str) -> dict:
            return send_handler._WRONG_CLASS_SENTINEL

        monkeypatch.setattr(send_handler, "_extract_via_llm", wrong_class)

        result = await send_handler.handle("how does the send message handler work?")

        assert result is send_handler._WRONG_CLASS_SENTINEL
        assert result == {"wrong_class": True}

    @pytest.mark.asyncio
    async def test_without_params_uses_llm_extraction_then_contact_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        llm_calls: list[tuple[str, str]] = []

        async def fake_extract(prompt: str, context: str) -> dict[str, Any]:
            llm_calls.append((prompt, context))
            return {"recipient": "mom", "body": "I'm here", "coherent": True}

        monkeypatch.setattr(send_handler, "_extract_via_llm", fake_extract)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle("let mom know I'm here", context="Earlier turn")

        payload = _direct_send_payload(_result_text(result))
        assert payload == {"phone_number": "+15557654321", "body": "I'm here"}
        assert llm_calls == [("let mom know I'm here", "Earlier turn")]


class TestConfirmOrReviseResume:
    @pytest.mark.asyncio
    async def test_resume_yes_sends_existing_draft_directly_and_ends(self) -> None:
        result = await send_handler.handle("yes", pending=_send_confirmation_pending())

        text = _result_text(result)
        payload = _direct_send_payload(text)
        assert payload == {"phone_number": "+15551234567", "body": "I love you"}
        assert result["conversation_end"] is True
        assert result["structured"]["safety"] == {
            "side_effectful": True,
            "requires_confirmation": False,
        }

    @pytest.mark.asyncio
    async def test_resume_yes_with_incomplete_draft_abandons_to_stage3(self) -> None:
        pending = _send_confirmation_pending(phone="", body="I love you")

        result = await send_handler.handle("yes", pending=pending)

        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_resume_no_requests_updated_message_without_sending(self) -> None:
        result = await send_handler.handle("no", pending=_send_confirmation_pending())

        text = _result_text(result)
        assert text == "Please give me the updated message."
        assert "[[CLIENT_TOOL:" not in text
        pending = result["structured"]["pending_action"]
        assert pending["awaiting"] == "revised_body"
        assert pending["data"]["draft"] == {
            "phone": "+15551234567",
            "display": "Kathia",
        }

    @pytest.mark.asyncio
    async def test_resume_cancel_ends_without_sending(self) -> None:
        result = await send_handler.handle("cancel", pending=_send_confirmation_pending())

        text = _result_text(result)
        assert text == "Ok."
        assert "[[CLIENT_TOOL:" not in text
        assert result["conversation_end"] is True
        assert result["structured"] == {"intent": "send message"}

    @pytest.mark.asyncio
    async def test_unrecognized_confirmation_reply_abandons_to_stage3(self) -> None:
        result = await send_handler.handle(
            "what do you think?", pending=_send_confirmation_pending()
        )

        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_revised_body_slot_treats_one_word_yes_as_message_body(self) -> None:
        result = await send_handler.handle("yes", pending=_revised_body_pending())

        text = _result_text(result)
        assert text == "Message to Kathia: yes. Should I send it?"
        assert "[[CLIENT_TOOL:" not in text
        pending = result["structured"]["pending_action"]
        assert pending["awaiting"] == "send_confirmation"
        assert pending["data"]["draft"] == {
            "phone": "+15551234567",
            "display": "Kathia",
            "body": "yes",
        }

    @pytest.mark.asyncio
    async def test_empty_revised_body_abandons_to_stage3(self) -> None:
        result = await send_handler.handle("   ", pending=_revised_body_pending())

        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_unknown_pending_awaiting_abandons_to_stage3(self) -> None:
        result = await send_handler.handle(
            "anything",
            pending={
                "handler_class": "send message",
                "awaiting": "unexpected",
                "data": {"awaiting": "unexpected"},
            },
        )

        assert result == {"abandon_pending": True, "force_stage3": True}


class TestOpenDraftSafetyNet:
    def _install_open_draft(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pending_action: dict[str, Any],
    ) -> None:
        from jane_web import session_context
        from vault_web import recent_turns

        monkeypatch.setattr(session_context, "get_current_session_id", lambda: "session-1")
        monkeypatch.setattr(
            recent_turns,
            "get_active_state",
            lambda session_id: {"pending_action": pending_action},
        )

    def test_confirm_open_client_draft_emits_sms_send_with_existing_draft_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_open_draft(
            monkeypatch,
            {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "data": {
                    "draft_id": "draft-123",
                    "query": "Kathia",
                    "body": "I love you",
                },
            },
        )

        result = send_handler._check_open_draft("yes")

        text = _result_text(result)
        tool, payload = _sms_tool(text)
        assert tool == "sms_send"
        assert payload == {"draft_id": "draft-123"}
        assert "sms_send_direct" not in text
        assert result["structured"]["pending_action"] == {
            "type": "SEND_MESSAGE_DRAFT_OPEN",
            "status": "resolved",
            "resolution": "sent",
        }

    def test_cancel_open_client_draft_requires_strong_cancel_phrase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_open_draft(
            monkeypatch,
            {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "data": {
                    "draft_id": "draft-456",
                    "query": "Mom",
                    "body": "Running late",
                },
            },
        )

        assert send_handler._check_open_draft("no") is None
        result = send_handler._check_open_draft("cancel")

        text = _result_text(result)
        tool, payload = _sms_tool(text)
        assert tool == "sms_cancel"
        assert payload == {"draft_id": "draft-456"}
        assert result["structured"]["pending_action"]["resolution"] == "cancelled"

    def test_edit_open_client_draft_escalates_to_stage3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_open_draft(
            monkeypatch,
            {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "data": {
                    "draft_id": "draft-789",
                    "query": "Mom",
                    "body": "Running late",
                },
            },
        )

        result = send_handler._check_open_draft("change it to say leaving now")

        assert result is None


class TestExtractionParsingAndCoherence:
    def test_parse_wrong_class_sentinel(self) -> None:
        assert send_handler._parse_extraction("WRONG_CLASS") is send_handler._WRONG_CLASS_SENTINEL

    def test_parse_structured_llm_output(self) -> None:
        result = send_handler._parse_extraction(
            "RECIPIENT: mom\nBODY: I'm on my way\nCOHERENT: yes"
        )

        assert result == {
            "recipient": "mom",
            "body": "I'm on my way",
            "coherent": True,
        }

    def test_parse_missing_body_uses_none_sentinel(self) -> None:
        result = send_handler._parse_extraction("RECIPIENT: wife\nCOHERENT: yes")

        assert result == {"recipient": "wife", "body": "(none)", "coherent": True}

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "BODY: hello\nCOHERENT: yes",
            "RECIPIENT:\nBODY: hello\nCOHERENT: yes",
            "garbage without labels",
        ],
    )
    def test_parse_malformed_output_returns_none(self, raw: str) -> None:
        assert send_handler._parse_extraction(raw) is None

    @pytest.mark.parametrize(
        "raw",
        [
            "RECIPIENT: mom\nBODY: I will be at the\nCOHERENT: yes",
            "RECIPIENT: mom\nBODY: uh I am coming\nCOHERENT: yes",
            "RECIPIENT: mom\nBODY: Alexa cancel that\nCOHERENT: yes",
            "RECIPIENT: mom\nBODY: I am coming\nCOHERENT: no",
        ],
    )
    def test_parse_marks_incoherent_when_llm_or_rules_reject_body(self, raw: str) -> None:
        result = send_handler._parse_extraction(raw)

        assert result is not None
        assert result["coherent"] is False

    @pytest.mark.parametrize("ending", sorted(send_handler._DANGLING_ENDINGS))
    def test_every_dangling_ending_is_reachable_by_coherence_rules(
        self, ending: str
    ) -> None:
        assert send_handler._is_coherent(f"I will meet you {ending}") is False

    @pytest.mark.parametrize("filler", sorted(send_handler._FILLER_WORDS))
    def test_every_filler_word_is_reachable_by_coherence_rules(self, filler: str) -> None:
        assert send_handler._is_coherent(f"I am {filler} almost there") is False

    @pytest.mark.parametrize("command", sorted(send_handler._DEVICE_COMMANDS))
    def test_every_background_device_command_is_reachable_by_coherence_rules(
        self, command: str
    ) -> None:
        assert send_handler._is_coherent(f"{command} cancel my alarm") is False

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "(none)",
            "Alexander can meet tomorrow",
            "Alexandra can meet tomorrow",
            "Sirius is visible tonight",
        ],
    )
    def test_coherence_allows_empty_body_and_non_command_substrings(self, body: str) -> None:
        assert send_handler._is_coherent(body) is True


class TestLlmAndDbIntegrationPoints:
    @pytest.mark.asyncio
    async def test_extract_via_llm_posts_expected_payload_and_records_activity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from jane_web.jane_v2 import models

        calls: list[dict[str, Any]] = []
        activity: list[str] = []

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, str]:
                return {
                    "response": (
                        "RECIPIENT: mom\n"
                        "BODY: I'm on my way\n"
                        "COHERENT: yes"
                    )
                }

        class FakeAsyncClient:
            def __init__(self, *, timeout: float):
                self.timeout = timeout

            async def __aenter__(self) -> "FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                return False

            async def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
                calls.append({"url": url, "json": json, "timeout": self.timeout})
                return FakeResponse()

        monkeypatch.setattr(send_handler.httpx, "AsyncClient", FakeAsyncClient)
        monkeypatch.setattr(
            models,
            "record_ollama_activity",
            lambda: activity.append("recorded"),
            raising=False,
        )

        result = await send_handler._extract_via_llm(
            "let mom know I'm on my way", "Jane asked about travel."
        )

        assert result == {
            "recipient": "mom",
            "body": "I'm on my way",
            "coherent": True,
        }
        assert activity == ["recorded"]
        assert len(calls) == 1
        payload = calls[0]["json"]
        assert calls[0]["url"] == send_handler.OLLAMA_URL
        assert payload["model"] == send_handler.MODEL
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["options"]["temperature"] == 0.0
        assert payload["options"]["num_predict"] == 100
        assert "Recent conversation:\nJane asked about travel." in payload["prompt"]
        assert "User: let mom know I'm on my way" in payload["prompt"]

    @pytest.mark.asyncio
    async def test_extract_via_llm_http_error_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeAsyncClient:
            def __init__(self, *, timeout: float):
                self.timeout = timeout

            async def __aenter__(self) -> "FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                return False

            async def post(self, url: str, json: dict[str, Any]) -> None:
                raise RuntimeError("ollama unavailable")

        monkeypatch.setattr(send_handler.httpx, "AsyncClient", FakeAsyncClient)

        assert await send_handler._extract_via_llm("text mom hi", "") is None

    @pytest.mark.asyncio
    async def test_contact_resolution_from_contacts_queries_alias_table_and_writes_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vault_web import database

        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        add_alias_calls: list[tuple[str, str, str | None]] = []
        fake_conn = _FakeConnection(row=None)

        _install_recipient_resolution(
            monkeypatch,
            {
                "Lee": {
                    "phone_number": "+15550001111",
                    "display_name": "Lee Nguyen",
                    "source": "contacts",
                }
            },
        )
        monkeypatch.setattr(database, "get_db", lambda: fake_conn)
        monkeypatch.setattr(
            sms_helpers,
            "add_alias",
            lambda alias, phone, display_name=None: add_alias_calls.append(
                (alias, phone, display_name)
            )
            or True,
        )

        result = await send_handler.handle(
            "text Lee I am running late",
            params={"recipient": "Lee", "body": "I am running late", "intent_kind": "send"},
        )

        assert _direct_send_payload(_result_text(result)) == {
            "phone_number": "+15550001111",
            "body": "I am running late",
        }
        assert len(fake_conn.executed) == 1
        sql, params = fake_conn.executed[0]
        assert "SELECT 1 FROM contact_aliases" in sql
        assert params == ("lee",)
        assert add_alias_calls == [("lee", "+15550001111", "Lee Nguyen")]

    @pytest.mark.asyncio
    async def test_existing_alias_row_prevents_auto_alias_overwrite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vault_web import database

        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        fake_conn = _FakeConnection(row={"1": 1})
        add_alias_calls: list[tuple[Any, ...]] = []

        _install_recipient_resolution(
            monkeypatch,
            {
                "Lee": {
                    "phone_number": "+15550001111",
                    "display_name": "Lee Nguyen",
                    "source": "contacts",
                }
            },
        )
        monkeypatch.setattr(database, "get_db", lambda: fake_conn)
        monkeypatch.setattr(
            sms_helpers,
            "add_alias",
            lambda *args, **kwargs: add_alias_calls.append((args, kwargs)) or True,
        )

        result = await send_handler.handle(
            "text Lee I am running late",
            params={"recipient": "Lee", "body": "I am running late", "intent_kind": "send"},
        )

        assert _direct_send_payload(_result_text(result))["phone_number"] == "+15550001111"
        assert add_alias_calls == []


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_input_without_metadata_escalates_when_extractor_declines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)

        async def fake_extract(prompt: str, context: str) -> None:
            assert prompt == ""
            assert context == ""
            return None

        monkeypatch.setattr(send_handler, "_extract_via_llm", fake_extract)

        assert await send_handler.handle("") is None

    @pytest.mark.asyncio
    async def test_none_prompt_can_escalate_when_extractor_declines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)

        async def fake_extract(prompt: None, context: str) -> None:
            assert prompt is None
            assert context == ""
            return None

        monkeypatch.setattr(send_handler, "_extract_via_llm", fake_extract)

        assert await send_handler.handle(None) is None  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_malformed_params_object_raises_instead_of_sending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)

        class BadParams:
            pass

        with pytest.raises(AttributeError):
            await send_handler.handle("text mom hi", params=BadParams())  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_very_long_body_round_trips_in_direct_send_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        long_body = "x" * 12000
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom " + long_body,
            params={"recipient": "mom", "body": long_body, "intent_kind": "send"},
        )

        payload = _direct_send_payload(_result_text(result))
        assert payload == {"phone_number": "+15557654321", "body": long_body}


class TestStructuralMappingInvariants:
    def test_send_message_class_is_wired_across_stage1_dispatcher_and_registry(
        self,
    ) -> None:
        registry = class_registry.get_registry(refresh=True)

        assert stage1_classifier._CLASS_MAP["SEND_MESSAGE"] == "send message"
        assert stage2_dispatcher._CLASS_DESCRIPTIONS["send message"]
        assert send_metadata.METADATA["name"] == "send message"
        assert "send message" in registry
        assert registry["send message"]["pkg_name"] == "send_message"
        assert registry["send message"]["handler"] is send_handler.handle

    def test_sms_related_stage1_keys_do_not_map_to_fallback_or_wrong_sms_class(
        self,
    ) -> None:
        expected = {
            "SEND_MESSAGE": "send message",
            "READ_MESSAGES": "read messages",
            "SYNC_MESSAGES": "sync messages",
        }

        contradictions = {
            key: stage1_classifier._CLASS_MAP.get(key)
            for key, value in expected.items()
            if stage1_classifier._CLASS_MAP.get(key) != value
        }

        assert contradictions == {}

    def test_every_stage1_non_fallback_value_exists_in_class_registry(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        mapped_values = {
            value
            for value in stage1_classifier._CLASS_MAP.values()
            if value != "others"
        }

        assert mapped_values <= set(registry)

    def test_every_stage1_class_map_value_is_reachable_from_at_least_one_key(self) -> None:
        reverse: dict[str, list[str]] = {}
        for key, value in stage1_classifier._CLASS_MAP.items():
            reverse.setdefault(value, []).append(key)

        unreachable_values = [
            value for value in set(stage1_classifier._CLASS_MAP.values()) if not reverse[value]
        ]

        assert unreachable_values == []

    def test_every_dispatch_description_key_exists_in_registry(self) -> None:
        registry = class_registry.get_registry(refresh=True)

        assert set(stage2_dispatcher._CLASS_DESCRIPTIONS) <= set(registry)

    def test_registered_classes_have_handler_or_documented_escalation(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        undocumented = {
            name
            for name, meta in registry.items()
            if meta.get("handler") is None and name not in DOCUMENTED_NO_HANDLER_ESCALATES
        }

        assert undocumented == set()

    def test_no_sms_protocol_reference_uses_contacts_call(self, module_source: str) -> None:
        description = send_metadata.METADATA["description"]
        escalation_context = send_metadata.METADATA["escalation_context"]

        assert "contacts.call" not in module_source
        assert "contacts.call" not in description
        assert "contacts.call" not in escalation_context

    def test_send_metadata_references_only_existing_neighbor_sms_classes(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        description = send_metadata.METADATA["description"]
        referenced = {
            class_name
            for class_name in ("others", "read messages", "sync messages", "send message")
            if class_name in description or class_name == "send message"
        }

        assert referenced <= set(registry)


class TestDestructiveOperationInvariants:
    def test_direct_send_marker_has_exact_tool_and_json_shape(self) -> None:
        marker = send_handler._build_send_marker("+15551234567", "I love you")

        payload = _direct_send_payload(marker)
        assert marker.startswith("[[CLIENT_TOOL:contacts.sms_send_direct:")
        assert marker.endswith("]]")
        assert payload == {"phone_number": "+15551234567", "body": "I love you"}

    def test_source_direct_send_surface_requires_numeric_confidence_threshold(
        self, module_source: str
    ) -> None:
        destructive_present = "[[CLIENT_TOOL:contacts.sms_send_direct" in module_source
        numeric_threshold_guard = bool(
            re.search(
                r"(confidence|conf|score|probability|min_dist)[\s\S]{0,80}"
                r"(>=\s*0\.80|>=\s*0\.8|<=\s*0\.20|<=\s*0\.2)",
                module_source,
                re.IGNORECASE,
            )
        )

        assert not destructive_present or numeric_threshold_guard

    @pytest.mark.asyncio
    async def test_direct_send_cannot_fire_on_borderline_numeric_confidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom I'm here",
            params={
                "recipient": "mom",
                "body": "I'm here",
                "intent_kind": "send",
                "confidence": 0.79,
            },
        )

        _assert_no_client_tool(result)

    @pytest.mark.asyncio
    async def test_direct_send_cannot_fire_on_string_high_confidence_without_score(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom I'm here",
            params={
                "recipient": "mom",
                "body": "I'm here",
                "intent_kind": "send",
                "confidence": "High",
            },
        )

        _assert_no_client_tool(result)

    @pytest.mark.asyncio
    async def test_ambiguous_ask_intent_cannot_fire_direct_send(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "ask mom if she is coming",
            params={
                "recipient": "mom",
                "body": "Are you coming?",
                "intent_kind": "ask",
                "confidence": 0.99,
            },
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_borderline_incoherent_body_cannot_fire_direct_send(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_open_draft(monkeypatch)
        _block_llm_extraction(monkeypatch)
        _install_recipient_resolution(
            monkeypatch,
            {
                "mom": {
                    "phone_number": "+15557654321",
                    "display_name": "Mom",
                    "source": "alias",
                }
            },
        )

        result = await send_handler.handle(
            "text mom yeah",
            params={"recipient": "mom", "body": "yeah", "intent_kind": "send"},
        )

        _assert_no_client_tool(result)
        assert isinstance(result, dict)
        assert result["structured"]["pending_action"]["awaiting"] == "send_confirmation"


class TestHandlerDispatchShape:
    @pytest.mark.asyncio
    async def test_dispatcher_invokes_registered_send_handler_and_returns_text_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def gate_pass(*_args: Any) -> bool:
            return True

        async def fake_handle(
            prompt: str,
            *,
            context: str = "",
            pending: dict | None = None,
            params: dict | None = None,
        ) -> dict[str, str]:
            assert prompt == "text mom hi"
            assert context == "ctx"
            assert pending is None
            assert params == {"recipient": "mom", "body": "hi"}
            return {"text": "ok"}

        monkeypatch.setattr(
            class_registry,
            "get_registry",
            lambda refresh=False: {"send message": {"handler": fake_handle}},
        )
        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate_pass)

        result = await stage2_dispatcher.dispatch(
            "send message",
            "text mom hi",
            context="ctx",
            min_dist=0.5,
            params={"recipient": "mom", "body": "hi"},
        )

        assert result == {"text": "ok"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_result",
        [
            {},
            {"response": "missing text"},
            {"wrong_class": True},
            None,
        ],
    )
    async def test_dispatcher_filters_handler_returns_without_text(
        self, monkeypatch: pytest.MonkeyPatch, bad_result: Any
    ) -> None:
        async def gate_pass(*_args: Any) -> bool:
            return True

        async def fake_handle(_prompt: str) -> Any:
            return bad_result

        monkeypatch.setattr(
            class_registry,
            "get_registry",
            lambda refresh=False: {"send message": {"handler": fake_handle}},
        )
        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate_pass)
        monkeypatch.setattr(
            stage2_dispatcher,
            "_self_correct_classification",
            lambda *_args: None,
        )

        result = await stage2_dispatcher.dispatch(
            "send message", "text mom hi", min_dist=0.5
        )

        assert result is None

    def test_all_actual_registered_handlers_are_callable_or_documented_no_handler(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        violations: dict[str, Any] = {}

        for name, meta in registry.items():
            handler = meta.get("handler")
            if handler is None:
                if name not in DOCUMENTED_NO_HANDLER_ESCALATES:
                    violations[name] = "missing handler without documented escalation"
            elif not callable(handler):
                violations[name] = f"handler is not callable: {handler!r}"

        assert violations == {}

    def test_destructive_registered_classes_are_not_documented_as_fallback_others(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        contradictions = {
            name: registry[name]
            for name in DESTRUCTIVE_CLASS_NAMES
            if name in registry and registry[name]["name"] == "others"
        }

        assert contradictions == {}
