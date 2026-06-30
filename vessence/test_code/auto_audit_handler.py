"""Auto-audit tests for jane_web.jane_v2.classes.send_message.handler."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

MODULE_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/send_message/handler.py"
SPEC_PATH = VESSENCE_ROOT / "CLAUDE.md"

handler = importlib.import_module("jane_web.jane_v2.classes.send_message.handler")


DIRECT_TOOL = "contacts.sms_send_direct"
SEND_TOOL = "contacts.sms_send"
CANCEL_TOOL = "contacts.sms_cancel"
DOCUMENTED_NO_HANDLER_ESCALATORS = {
    "delegate opus",
    "delete email",
    "end conversation",
    "others",
    "read email",
    "send email",
    "unclear",
}


class _FakeOllamaResponse:
    def __init__(self, payload: dict | None = None, *, status_error: Exception | None = None):
        self._payload = payload if payload is not None else {"response": ""}
        self.raise_for_status = MagicMock(side_effect=status_error)

    def json(self) -> dict:
        return self._payload


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, *, existing_alias: bool = False):
        self.existing_alias = existing_alias
        self.queries: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()):
        self.queries.append((sql, params))
        return _FakeCursor((1,) if self.existing_alias else None)


class _FakeDBContext:
    def __init__(self, conn: _FakeConnection):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def install_ollama(monkeypatch):
    clients = []

    def _install(
        response_text: str = "",
        *,
        payload: dict | None = None,
        post_side_effect: Exception | None = None,
        status_error: Exception | None = None,
    ):
        class _FakeAsyncClient:
            def __init__(self, timeout=None, **kwargs):
                self.timeout = timeout
                self.kwargs = kwargs
                response = _FakeOllamaResponse(
                    payload if payload is not None else {"response": response_text},
                    status_error=status_error,
                )
                self.post = AsyncMock(return_value=response)
                if post_side_effect is not None:
                    self.post.side_effect = post_side_effect
                clients.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(handler.httpx, "AsyncClient", _FakeAsyncClient)
        return clients

    return _install


@pytest.fixture
def unexpected_ollama(monkeypatch):
    calls = []

    class _UnexpectedAsyncClient:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("unexpected Ollama call")

    monkeypatch.setattr(handler.httpx, "AsyncClient", _UnexpectedAsyncClient)
    return calls


def _source_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text())


def _source_text() -> str:
    return MODULE_PATH.read_text()


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _direct_marker_payload(text: str, tool: str = DIRECT_TOOL) -> dict:
    match = re.search(
        r"\[\[CLIENT_TOOL:" + re.escape(tool) + r":(?P<payload>\{.*?\})\]\]",
        text,
    )
    assert match, text
    return json.loads(match.group("payload"))


def _has_tool_marker(result: dict | None, tool: str = DIRECT_TOOL) -> bool:
    return isinstance(result, dict) and tool in str(result.get("text", ""))


def _install_sms_helpers(monkeypatch, *, resolved=None, add_alias_return: bool = True):
    import agent_skills.sms_helpers as sms_helpers

    calls = {"resolve": [], "add_alias": []}

    def resolve_recipient(name):
        calls["resolve"].append(name)
        value = resolved(name) if callable(resolved) else resolved
        return dict(value) if value else None

    def add_alias(alias, phone_number, display_name=None):
        calls["add_alias"].append((alias, phone_number, display_name))
        return add_alias_return

    monkeypatch.setattr(sms_helpers, "resolve_recipient", resolve_recipient)
    monkeypatch.setattr(sms_helpers, "add_alias", add_alias)
    return calls


def _install_fake_vault_database(monkeypatch, *, existing_alias: bool = False):
    conn = _FakeConnection(existing_alias=existing_alias)
    database_mod = types.ModuleType("vault_web.database")
    database_mod.get_db = lambda: _FakeDBContext(conn)
    monkeypatch.setitem(sys.modules, "vault_web.database", database_mod)
    return conn


def _install_open_draft_state(monkeypatch, *, state: dict, session_id: str | None = "session-1"):
    recent_turns_mod = types.ModuleType("vault_web.recent_turns")
    recent_turns_mod.get_active_state = lambda sid: state

    session_context_mod = types.ModuleType("jane_web.session_context")
    session_context_mod.get_current_session_id = lambda: session_id

    resolver_mod = types.ModuleType("jane_web.jane_v2.pending_action_resolver")
    resolver_mod._normalize = lambda text: re.sub(r"[^\w\s']", "", (text or "").strip().lower())
    resolver_mod._STAGE3_CANCEL_STRONG = {"cancel", "nevermind", "never mind", "stop"}
    resolver_mod._is_confirm = lambda text: resolver_mod._normalize(text) in {
        "yes",
        "yes send it",
        "send it",
    }
    resolver_mod._is_cancel = lambda text: resolver_mod._normalize(text) in {
        "cancel",
        "nevermind",
        "never mind",
        "stop",
    }
    resolver_mod._is_edit_intent = lambda text: "change" in resolver_mod._normalize(text)

    monkeypatch.setitem(sys.modules, "vault_web.recent_turns", recent_turns_mod)
    monkeypatch.setitem(sys.modules, "jane_web.session_context", session_context_mod)
    monkeypatch.setitem(sys.modules, "jane_web.jane_v2.pending_action_resolver", resolver_mod)


def _resolved_contact(
    *,
    phone: str = "+15551234567",
    display: str = "Kathia Wu",
    source: str = "alias",
) -> dict:
    return {"phone_number": phone, "display_name": display, "source": source}


class TestDocumentedBehavior:
    def test_claude_sms_protocol_documents_the_direct_send_contract(self):
        spec = SPEC_PATH.read_text()
        spec_lower = spec.lower()

        assert "Text Message (SMS) Protocols" in spec
        assert "Tell X something" in spec
        assert "ALWAYS SMS" in spec
        assert "contacts.call" in spec
        assert "sms_send_direct" in spec
        assert "do not use `sms_draft` or `sms_send`" in spec_lower
        assert "Rewrite perspective before sending" in spec

    def test_module_docstring_documents_fast_confirm_and_escalate_paths(self):
        doc = inspect.getdoc(handler)

        assert doc is not None
        assert "Fast path" in doc
        assert "Confirm-or-revise" in doc
        assert "Escalate" in doc
        assert "conversation_end=True" in doc
        assert "force_stage3" in doc

    @pytest.mark.asyncio
    async def test_fast_path_sends_direct_sms_and_returns_documented_shape(
        self, monkeypatch, unexpected_ollama
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact())

        result = await handler.handle(
            "text my wife I am on my way",
            params={
                "recipient": "my wife",
                "body": "I am on my way",
                "intent_kind": "send",
                "confidence": 0.80,
            },
        )

        assert result["text"].startswith("Done, message sent.")
        assert result["conversation_end"] is True
        assert result["structured"]["intent"] == "send message"
        assert result["structured"]["safety"] == {
            "side_effectful": True,
            "requires_confirmation": False,
        }
        payload = _direct_marker_payload(result["text"])
        assert payload == {"phone_number": "+15551234567", "body": "I am on my way"}
        assert "contacts.call" not in result["text"]
        assert unexpected_ollama == []

    @pytest.mark.asyncio
    async def test_ask_intent_escalates_for_stage3_draft_confirmation(
        self, monkeypatch, unexpected_ollama
    ):
        calls = _install_sms_helpers(monkeypatch, resolved=_resolved_contact())

        result = await handler.handle(
            "ask Lee what time she is coming",
            params={
                "recipient": "Lee",
                "body": "What time are you coming?",
                "intent_kind": "ask",
                "confidence": 0.99,
            },
        )

        assert result is None
        assert calls["resolve"] == []
        assert unexpected_ollama == []

    @pytest.mark.asyncio
    async def test_missing_recipient_escalates_to_stage3(self, monkeypatch, unexpected_ollama):
        calls = _install_sms_helpers(monkeypatch, resolved=_resolved_contact())

        result = await handler.handle(
            "text I am late",
            params={"recipient": "", "body": "I am late", "intent_kind": "send", "confidence": 0.99},
        )

        assert result is None
        assert calls["resolve"] == []
        assert unexpected_ollama == []

    @pytest.mark.asyncio
    async def test_unresolved_recipient_escalates_to_stage3(self, monkeypatch):
        calls = _install_sms_helpers(monkeypatch, resolved=None)

        result = await handler.handle(
            "text romeo hello",
            params={
                "recipient": "romeo",
                "body": "Hello",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result is None
        assert calls["resolve"] == ["romeo"]

    @pytest.mark.asyncio
    async def test_missing_body_escalates_without_sending(self, monkeypatch):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Mom"))

        result = await handler.handle(
            "text mom",
            params={"recipient": "mom", "body": "", "intent_kind": "send", "confidence": 0.99},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_incoherent_body_creates_confirm_or_revise_followup_not_direct_send(
        self, monkeypatch
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(
            "text Kathia I am uh",
            params={
                "recipient": "Kathia",
                "body": "I am uh",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result["text"] == "Message to Kathia: I am uh. Should I send it?"
        assert DIRECT_TOOL not in result["text"]
        pending = result["structured"]["pending_action"]
        assert pending["type"] == "STAGE2_FOLLOWUP"
        assert pending["handler_class"] == "send message"
        assert pending["awaiting"] == "send_confirmation"
        assert pending["data"]["draft"] == {
            "phone": "+15551234567",
            "display": "Kathia",
            "body": "I am uh",
        }

    @pytest.mark.asyncio
    async def test_llm_fallback_fast_path_uses_extracted_recipient_and_body(
        self, monkeypatch, install_ollama
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Mom"))
        install_ollama("RECIPIENT: mom\nBODY: I'm on my way\nCOHERENT: yes")

        result = await handler.handle("let mom know I'm on my way")

        assert result["conversation_end"] is True
        payload = _direct_marker_payload(result["text"])
        assert payload == {"phone_number": "+15551234567", "body": "I'm on my way"}


class TestFollowupResumeBehavior:
    @pytest.fixture
    def pending_confirmation(self):
        return {
            "handler_class": "send message",
            "awaiting": "send_confirmation",
            "data": {
                "draft": {
                    "phone": "+15551234567",
                    "display": "Kathia",
                    "body": "I am on my way",
                }
            },
        }

    @pytest.mark.asyncio
    async def test_resume_yes_sends_and_ends_conversation(self, pending_confirmation):
        result = await handler.handle("yes", pending=pending_confirmation)

        assert result["text"].startswith("Done.")
        assert result["conversation_end"] is True
        assert result["structured"]["safety"] == {
            "side_effectful": True,
            "requires_confirmation": False,
        }
        payload = _direct_marker_payload(result["text"])
        assert payload == {"phone_number": "+15551234567", "body": "I am on my way"}

    @pytest.mark.asyncio
    async def test_resume_yes_with_incomplete_draft_abandons_to_stage3(self):
        pending = {
            "handler_class": "send message",
            "awaiting": "send_confirmation",
            "data": {"draft": {"phone": "", "display": "Kathia", "body": "Hi"}},
        }

        result = await handler.handle("yes", pending=pending)

        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_resume_no_requests_updated_message_body(self, pending_confirmation):
        result = await handler.handle("no", pending=pending_confirmation)

        assert result["text"] == "Please give me the updated message."
        pending = result["structured"]["pending_action"]
        assert pending["type"] == "STAGE2_FOLLOWUP"
        assert pending["handler_class"] == "send message"
        assert pending["awaiting"] == "revised_body"
        assert pending["data"]["draft"] == {
            "phone": "+15551234567",
            "display": "Kathia",
        }

    @pytest.mark.asyncio
    async def test_resume_cancel_ends_without_sms_marker(self, pending_confirmation):
        result = await handler.handle("cancel", pending=pending_confirmation)

        assert result == {
            "text": "Ok.",
            "conversation_end": True,
            "structured": {"intent": "send message"},
        }

    @pytest.mark.asyncio
    async def test_resume_ambiguous_confirmation_abandons_to_stage3(self, pending_confirmation):
        result = await handler.handle("maybe in a minute", pending=pending_confirmation)

        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_revised_body_slot_treats_yes_as_message_text_not_confirmation(self):
        pending = {
            "handler_class": "send message",
            "awaiting": "revised_body",
            "data": {"draft": {"phone": "+15551234567", "display": "Kathia"}},
        }

        result = await handler.handle("yes", pending=pending)

        assert result["text"] == "Message to Kathia: yes. Should I send it?"
        assert DIRECT_TOOL not in result["text"]
        pending_action = result["structured"]["pending_action"]
        assert pending_action["awaiting"] == "send_confirmation"
        assert pending_action["data"]["draft"] == {
            "phone": "+15551234567",
            "display": "Kathia",
            "body": "yes",
        }

    @pytest.mark.asyncio
    async def test_revised_body_empty_abandons_to_stage3(self):
        pending = {
            "handler_class": "send message",
            "awaiting": "revised_body",
            "data": {"draft": {"phone": "+15551234567", "display": "Kathia"}},
        }

        result = await handler.handle("   ", pending=pending)

        assert result == {"abandon_pending": True, "force_stage3": True}


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_input_with_empty_body_escalates_without_destructive_marker(
        self, monkeypatch
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(
            "",
            params={"recipient": "Kathia", "body": "", "intent_kind": "send", "confidence": 0.99},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_none_prompt_does_not_emit_destructive_send(self, monkeypatch):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_none_body_param_escalates_without_sending(self, monkeypatch):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(
            "text Kathia",
            params={
                "recipient": "Kathia",
                "body": None,
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_llm_output_escalates_without_sending(self, install_ollama):
        install_ollama("not the requested structured format")

        result = await handler.handle("\x00\x00 ???")

        assert result is None

    @pytest.mark.asyncio
    async def test_very_long_prompt_uses_bounded_llm_generation_options(
        self, monkeypatch, install_ollama
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Sarah"))
        long_prompt = "text Sarah " + ("I will be a little late " * 600)
        clients = install_ollama("RECIPIENT: Sarah\nBODY: I will be a little late\nCOHERENT: yes")

        result = await handler.handle(long_prompt)

        assert result["conversation_end"] is True
        args, kwargs = clients[0].post.await_args
        assert args == (handler.OLLAMA_URL,)
        payload = kwargs["json"]
        assert payload["options"] == {
            "temperature": 0.0,
            "num_predict": 100,
            "num_ctx": handler.LOCAL_LLM_NUM_CTX,
        }
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["keep_alive"] == -1

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "BODY: hello\nCOHERENT: yes",
            "RECIPIENT:\nBODY: hello\nCOHERENT: yes",
            "RECIPIENT:   \nBODY: hello",
        ],
    )
    def test_malformed_extraction_returns_none(self, raw):
        assert handler._parse_extraction(raw) is None


class TestIntegrationPoints:
    @pytest.mark.asyncio
    async def test_llm_call_uses_shared_model_config_context_and_activity_recorder(
        self, monkeypatch, install_ollama
    ):
        from jane_web.jane_v2 import models

        record_activity = MagicMock()
        monkeypatch.setattr(models, "record_ollama_activity", record_activity)
        clients = install_ollama("RECIPIENT: Mom\nBODY: I'm home\nCOHERENT: yes")

        result = await handler._extract_via_llm(
            "let mom know I'm home",
            "User: where are you?\nJane: I asked mom.",
        )

        assert result == {"recipient": "Mom", "body": "I'm home", "coherent": True}
        assert len(clients) == 1
        assert clients[0].timeout == handler.LOCAL_LLM_TIMEOUT
        clients[0].post.assert_awaited_once()
        args, kwargs = clients[0].post.await_args
        assert args == (handler.OLLAMA_URL,)
        payload = kwargs["json"]
        assert payload["model"] == handler.MODEL
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["keep_alive"] == -1
        assert payload["options"] == {
            "temperature": 0.0,
            "num_predict": 100,
            "num_ctx": handler.LOCAL_LLM_NUM_CTX,
        }
        assert "Recent conversation:" in payload["prompt"]
        assert "User: where are you?" in payload["prompt"]
        assert "User: let mom know I'm home" in payload["prompt"]
        record_activity.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_llm_http_failure_escalates_as_none(self, install_ollama):
        install_ollama(post_side_effect=RuntimeError("ollama unavailable"))

        assert await handler._extract_via_llm("text Sarah hi", "") is None

    @pytest.mark.asyncio
    async def test_llm_status_failure_escalates_as_none(self, install_ollama):
        install_ollama(
            "RECIPIENT: Sarah\nBODY: Hi\nCOHERENT: yes",
            status_error=RuntimeError("500"),
        )

        assert await handler._extract_via_llm("text Sarah hi", "") is None

    @pytest.mark.asyncio
    async def test_auto_alias_queries_db_and_writes_alias_for_contact_resolution(
        self, monkeypatch
    ):
        calls = _install_sms_helpers(
            monkeypatch,
            resolved=_resolved_contact(display="Kathia Wu", source="contacts"),
        )
        conn = _install_fake_vault_database(monkeypatch, existing_alias=False)

        result = await handler.handle(
            "text my wife I am late",
            params={
                "recipient": "my wife",
                "body": "I am late",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result["conversation_end"] is True
        assert calls["resolve"] == ["my wife"]
        assert len(conn.queries) == 1
        sql, params = conn.queries[0]
        assert "SELECT 1 FROM contact_aliases" in sql
        assert params == ("wife",)
        assert calls["add_alias"] == [("wife", "+15551234567", "Kathia Wu")]

    @pytest.mark.asyncio
    async def test_existing_alias_prevents_auto_alias_overwrite(self, monkeypatch):
        calls = _install_sms_helpers(
            monkeypatch,
            resolved=_resolved_contact(display="Kathia Wu", source="contacts"),
        )
        _install_fake_vault_database(monkeypatch, existing_alias=True)

        result = await handler.handle(
            "text my wife I am late",
            params={
                "recipient": "my wife",
                "body": "I am late",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result["conversation_end"] is True
        assert calls["add_alias"] == []

    @pytest.mark.asyncio
    async def test_alias_source_does_not_query_alias_db_or_rewrite_alias(self, monkeypatch):
        calls = _install_sms_helpers(
            monkeypatch,
            resolved=_resolved_contact(display="Kathia Wu", source="alias"),
        )
        conn = _install_fake_vault_database(monkeypatch, existing_alias=False)

        result = await handler.handle(
            "text my wife I am late",
            params={
                "recipient": "my wife",
                "body": "I am late",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert result["conversation_end"] is True
        assert conn.queries == []
        assert calls["add_alias"] == []

    def test_open_draft_confirm_uses_draft_send_marker(self, monkeypatch):
        _install_open_draft_state(
            monkeypatch,
            state={
                "pending_action": {
                    "type": "SEND_MESSAGE_DRAFT_OPEN",
                    "data": {
                        "draft_id": "draft-123",
                        "query": "Kathia",
                        "body": "I am late",
                    },
                }
            },
        )

        result = handler._check_open_draft("yes send it")

        assert result["structured"]["pending_action"]["resolution"] == "sent"
        payload = _direct_marker_payload(result["text"], tool=SEND_TOOL)
        assert payload == {"draft_id": "draft-123"}

    def test_open_draft_cancel_uses_cancel_marker(self, monkeypatch):
        _install_open_draft_state(
            monkeypatch,
            state={
                "pending_action": {
                    "type": "SEND_MESSAGE_DRAFT_OPEN",
                    "data": {"draft_id": "draft-123", "query": "Kathia", "body": "Hi"},
                }
            },
        )

        result = handler._check_open_draft("cancel")

        assert result["structured"]["pending_action"]["resolution"] == "cancelled"
        payload = _direct_marker_payload(result["text"], tool=CANCEL_TOOL)
        assert payload == {"draft_id": "draft-123"}

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_calls_send_message_handler_with_documented_shape(
        self, monkeypatch
    ):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage2_dispatcher

        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))
        registry = class_registry.get_registry(refresh=True)

        assert "send message" in registry
        assert registry["send message"]["handler"] is handler.handle
        assert registry["send message"].get("ack") is None

        result = await stage2_dispatcher.dispatch(
            "send message",
            "text Kathia I am on my way",
            min_dist=0.0,
            params={
                "recipient": "Kathia",
                "body": "I am on my way",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert isinstance(result, dict)
        assert isinstance(result["text"], str)
        assert result["text"].strip()
        assert DIRECT_TOOL in result["text"]


class TestParsingAndCoherence:
    def test_wrong_class_sentinel_is_parsed(self):
        assert handler._parse_extraction("WRONG_CLASS") is handler._WRONG_CLASS_SENTINEL

    def test_parse_extraction_preserves_rewritten_body_and_recipient(self):
        parsed = handler._parse_extraction(
            "RECIPIENT: wife\nBODY: I love you today\nCOHERENT: yes"
        )

        assert parsed == {"recipient": "wife", "body": "I love you today", "coherent": True}

    def test_parse_extraction_defaults_missing_body_to_none_sentinel(self):
        parsed = handler._parse_extraction("RECIPIENT: wife\nCOHERENT: yes")

        assert parsed == {"recipient": "wife", "body": "(none)", "coherent": True}

    @pytest.mark.parametrize(
        "body",
        [
            "I will be at",
            "I am uh",
            "Hey Siri remind me later",
            "ok google text Sarah",
            "Alexa stop",
        ],
    )
    def test_parse_extraction_marks_rule_detected_garbled_body_incoherent(self, body):
        parsed = handler._parse_extraction(f"RECIPIENT: Sarah\nBODY: {body}\nCOHERENT: yes")

        assert parsed == {"recipient": "Sarah", "body": body, "coherent": False}

    def test_llm_coherent_no_is_never_overridden_by_rules(self):
        parsed = handler._parse_extraction("RECIPIENT: Sarah\nBODY: Clear body\nCOHERENT: no")

        assert parsed == {"recipient": "Sarah", "body": "Clear body", "coherent": False}

    @pytest.mark.parametrize("body", [None, "", "(none)"])
    def test_empty_or_missing_body_is_coherent_intent_not_sendable_body(self, body):
        assert handler._is_coherent(body) is True

    @pytest.mark.parametrize("ending", sorted(handler._DANGLING_ENDINGS))
    def test_every_dangling_ending_is_reachable_by_coherence_rules(self, ending):
        assert handler._is_coherent(f"I will meet you {ending}") is False

    @pytest.mark.parametrize("filler", sorted(handler._FILLER_WORDS))
    def test_every_filler_word_is_reachable_by_coherence_rules(self, filler):
        assert handler._is_coherent(f"I am {filler} on my way") is False

    @pytest.mark.parametrize("command", handler._DEVICE_COMMANDS)
    def test_every_device_command_is_reachable_by_coherence_rules(self, command):
        assert handler._is_coherent(f"{command} remind me to text Sarah") is False

    @pytest.mark.parametrize(
        "body",
        [
            "Alexander said hello",
            "Alexandra is running late",
            "I talked to Alex about dinner",
            "I will be there soon.",
        ],
    )
    def test_device_command_filter_does_not_shadow_similar_contact_names(self, body):
        assert handler._is_coherent(body) is True


class TestStructuralInvariants:
    def test_direct_send_confidence_helper_requires_numeric_non_bool_at_least_080(self):
        rejected = [None, False, True, "High", "0.99", 0, 0.5, 0.799999]
        accepted = [0.80, 0.800001, 1, 1.0]

        assert [handler._has_direct_send_confidence(value) for value in rejected] == [
            False
        ] * len(rejected)
        assert [handler._has_direct_send_confidence(value) for value in accepted] == [
            True
        ] * len(accepted)

    @pytest.mark.parametrize("confidence", [0.0, 0.79, 0.799999, "High", True, False, None])
    @pytest.mark.asyncio
    async def test_borderline_or_non_numeric_confidence_cannot_fire_direct_send(
        self, monkeypatch, confidence
    ):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(
            "text Kathia I am on my way",
            params={
                "recipient": "Kathia",
                "body": "I am on my way",
                "intent_kind": "send",
                "confidence": confidence,
            },
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_confidence_cannot_fire_destructive_direct_send(self, monkeypatch):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle(
            "text Kathia I am on my way",
            params={"recipient": "Kathia", "body": "I am on my way", "intent_kind": "send"},
        )

        assert result is None

    @pytest.mark.parametrize(
        "params",
        [
            {"recipient": "", "body": "Hi", "intent_kind": "send", "confidence": 0.99},
            {"recipient": "Kathia", "body": "", "intent_kind": "send", "confidence": 0.99},
            {"recipient": "Kathia", "body": "I am uh", "intent_kind": "send", "confidence": 0.99},
            {"recipient": "Kathia", "body": "Hi", "intent_kind": "ask", "confidence": 0.99},
        ],
    )
    @pytest.mark.asyncio
    async def test_ambiguous_or_non_send_params_do_not_emit_direct_marker(self, monkeypatch, params):
        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))

        result = await handler.handle("text Kathia", params=params)

        assert not _has_tool_marker(result, DIRECT_TOOL)

    def test_build_send_marker_json_round_trips_special_characters(self):
        marker = handler._build_send_marker("+15551234567", 'He said "yes" ]].')

        payload = _direct_marker_payload(marker)
        assert payload == {"phone_number": "+15551234567", "body": 'He said "yes" ]].'}

    def test_no_phone_call_tool_is_reachable_from_send_message_handler_source(self):
        source = _source_text()

        assert "contacts.call" not in source
        assert "contacts.sms_send_direct" in source

    def test_destructive_marker_construction_is_centralized(self):
        tree = _source_tree()
        marker_functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body_text = ast.get_source_segment(_source_text(), node) or ""
                if "contacts.sms_send_direct" in body_text:
                    marker_functions.append(node.name)

        assert marker_functions == ["_build_send_marker"]

    def test_stage1_send_message_mapping_points_to_registered_non_fallback_class(self):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage1_classifier

        registry = class_registry.get_registry(refresh=True)

        assert stage1_classifier._CLASS_MAP["SEND_MESSAGE"] == "send message"
        assert stage1_classifier._CLASS_MAP["SEND_MESSAGE"] in registry
        assert stage1_classifier._CLASS_MAP["SEND_MESSAGE"] != "others"
        assert callable(registry["send message"]["handler"])

    def test_stage1_fallback_keys_do_not_contradict_send_message_routing(self):
        from jane_web.jane_v2 import stage1_classifier

        assert stage1_classifier._CLASS_MAP["DELEGATE_OPUS"] == "others"
        assert stage1_classifier._CLASS_MAP["FORCE_STAGE3"] == "others"
        assert stage1_classifier._CLASS_MAP["RESTART_SERVER"] == "others"
        assert stage1_classifier._CLASS_MAP["SEND_EMAIL"] == "send email"
        assert stage1_classifier._CLASS_MAP["READ_MESSAGES"] == "read messages"

    def test_every_stage1_class_map_value_exists_in_registry(self):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage1_classifier

        registry = class_registry.get_registry(refresh=True)
        missing = {
            stage1_name: registry_name
            for stage1_name, registry_name in stage1_classifier._CLASS_MAP.items()
            if registry_name not in registry
        }

        assert missing == {}

    def test_every_dispatch_description_key_exists_in_registry(self):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage2_dispatcher

        registry = class_registry.get_registry(refresh=True)

        assert set(stage2_dispatcher._CLASS_DESCRIPTIONS) <= set(registry)

    def test_no_handler_registry_entries_are_explicit_escalators(self):
        from jane_web.jane_v2 import classes as class_registry

        registry = class_registry.get_registry(refresh=True)
        no_handler = {name for name, meta in registry.items() if meta.get("handler") is None}

        assert no_handler == DOCUMENTED_NO_HANDLER_ESCALATORS

    @pytest.mark.asyncio
    async def test_registered_send_message_handler_returns_dict_with_text_key(self, monkeypatch):
        from jane_web.jane_v2 import classes as class_registry

        _install_sms_helpers(monkeypatch, resolved=_resolved_contact(display="Kathia"))
        registry = class_registry.get_registry(refresh=True)
        result = await registry["send message"]["handler"](
            "text Kathia I am on my way",
            params={
                "recipient": "Kathia",
                "body": "I am on my way",
                "intent_kind": "send",
                "confidence": 0.99,
            },
        )

        assert isinstance(result, dict)
        assert isinstance(result["text"], str)
        assert result["text"].strip()

    def test_send_message_params_schema_keys_are_stable_and_referenced(self):
        metadata_mod = importlib.import_module("jane_web.jane_v2.classes.send_message.metadata")
        schema_keys = set(metadata_mod.PARAMS_SCHEMA)

        assert schema_keys == {"recipient", "body", "intent_kind", "confirm_signal"}
        source = _source_text()
        for key in {"recipient", "body", "intent_kind", "confidence"}:
            assert f'params.get("{key}"' in source

    def test_send_message_metadata_documents_sms_not_call_disambiguation(self):
        metadata_mod = importlib.import_module("jane_web.jane_v2.classes.send_message.metadata")
        description = metadata_mod.METADATA["description"]

        assert "call my wife" in description
        assert "'others' (phone call, NOT SMS)" in description
        assert "what did my wife text me" in description
        assert "'read messages'" in description
