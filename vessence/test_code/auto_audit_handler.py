"""Comprehensive audit tests for jane_web.jane_v2.classes.send_message.handler.

Covers behavioral correctness, edge cases, integration mocks, and structural
invariants for the Stage 2 send_message handler.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Ensure the module is importable ──────────────────────────────────────────

_VESSENCE = Path(__file__).resolve().parents[1]
for p in [str(_VESSENCE), str(_VESSENCE / "agent_skills"), str(_VESSENCE / "vault_web")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jane_web.jane_v2.classes.send_message.handler import (
    _is_coherent,
    _parse_extraction,
    _check_open_draft,
    _extract_via_llm,
    _handle_resume,
    _build_send_marker,
    handle,
    _DANGLING_ENDINGS,
    _FILLER_WORDS,
    _DEVICE_COMMANDS,
    _WRONG_CLASS_SENTINEL,
    _EXTRACT_PROMPT,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BEHAVIORAL TESTS — _is_coherent
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsCoherent:
    """Verify the rule-based coherence checker per docstring spec."""

    def test_normal_message_is_coherent(self):
        assert _is_coherent("I love you") is True

    def test_greeting_is_coherent(self):
        assert _is_coherent("Hey, what's up?") is True

    def test_single_word_body_coherent(self):
        assert _is_coherent("Hello") is True

    def test_empty_string_is_coherent(self):
        assert _is_coherent("") is True

    def test_none_body_is_coherent(self):
        assert _is_coherent("(none)") is True

    def test_none_value_is_coherent(self):
        assert _is_coherent(None) is True

    def test_dangling_the(self):
        assert _is_coherent("I went to the") is False

    def test_dangling_and(self):
        assert _is_coherent("Pick up milk and") is False

    def test_dangling_with_punctuation(self):
        assert _is_coherent("I was thinking about the.") is False

    def test_dangling_because(self):
        assert _is_coherent("I can't come because") is False

    def test_filler_uh(self):
        assert _is_coherent("Tell him uh I'll be late") is False

    def test_filler_um(self):
        assert _is_coherent("Um can you pick up dinner") is False

    def test_filler_hmm(self):
        assert _is_coherent("I was hmm thinking about dinner") is False

    def test_filler_with_punctuation(self):
        assert _is_coherent("Well, um, I'll be there") is False

    def test_device_command_alexa(self):
        assert _is_coherent("I'll be home soon alexa set timer") is False

    def test_device_command_hey_siri(self):
        assert _is_coherent("Tell her hey siri call mom") is False

    def test_device_command_ok_google(self):
        assert _is_coherent("I'm coming ok google navigate home") is False

    def test_device_command_hey_google(self):
        assert _is_coherent("Almost there hey google play music") is False

    def test_alexa_as_contact_name_standalone(self):
        """Bare 'alexa' triggers the device-command check because it matches
        the word-boundary pattern. This is a known trade-off."""
        assert _is_coherent("alexa") is False

    def test_name_containing_alexa_substring(self):
        """'Alexander' should NOT trip 'alexa' because word boundaries differ."""
        assert _is_coherent("Hey Alexander, see you tonight") is True

    def test_alexandra_not_tripped(self):
        assert _is_coherent("Tell Alexandra I said hi") is True

    def test_whitespace_only(self):
        assert _is_coherent("   ") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BEHAVIORAL TESTS — _parse_extraction
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseExtraction:
    """Verify structured output parsing from the LLM response."""

    def test_valid_three_line_output(self):
        raw = "RECIPIENT: wife\nBODY: I love you\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["recipient"] == "wife"
        assert result["body"] == "I love you"
        assert result["coherent"] is True

    def test_coherent_no(self):
        raw = "RECIPIENT: mom\nBODY: I'll be\nCOHERENT: no"
        result = _parse_extraction(raw)
        assert result["coherent"] is False

    def test_wrong_class(self):
        raw = "WRONG_CLASS"
        assert _parse_extraction(raw) is _WRONG_CLASS_SENTINEL

    def test_wrong_class_case_insensitive(self):
        raw = "wrong_class"
        assert _parse_extraction(raw) is _WRONG_CLASS_SENTINEL

    def test_wrong_class_embedded_in_text(self):
        raw = "This is not a send intent. WRONG_CLASS detected."
        assert _parse_extraction(raw) is _WRONG_CLASS_SENTINEL

    def test_missing_recipient_returns_none(self):
        raw = "BODY: hello\nCOHERENT: yes"
        assert _parse_extraction(raw) is None

    def test_missing_body_defaults_to_none(self):
        raw = "RECIPIENT: dad\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["body"] == "(none)"

    def test_missing_coherent_defaults_to_true(self):
        raw = "RECIPIENT: john\nBODY: Hey there"
        result = _parse_extraction(raw)
        assert result["coherent"] is True

    def test_case_insensitive_labels(self):
        raw = "recipient: Sarah\nbody: Thanks\ncoherent: YES"
        result = _parse_extraction(raw)
        assert result["recipient"] == "Sarah"
        assert result["body"] == "Thanks"

    def test_extra_whitespace_and_blank_lines(self):
        raw = "\n  RECIPIENT:   john  \n\n  BODY:   Hey buddy  \n  COHERENT:   yes  \n"
        result = _parse_extraction(raw)
        assert result["recipient"] == "john"
        assert result["body"] == "Hey buddy"

    def test_empty_string(self):
        assert _parse_extraction("") is None

    def test_garbage_input(self):
        assert _parse_extraction("asdfghjkl 12345 !!!") is None

    def test_coherent_no_plus_rule_incoherent_body(self):
        """Both LLM and rules say incoherent."""
        raw = "RECIPIENT: wife\nBODY: I was going to the\nCOHERENT: no"
        result = _parse_extraction(raw)
        assert result["coherent"] is False

    def test_coherent_yes_but_rule_catches_filler(self):
        """LLM says yes but rules override with filler detection."""
        raw = "RECIPIENT: wife\nBODY: I uh love you\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["coherent"] is False

    def test_coherent_yes_but_rule_catches_dangling(self):
        """LLM says yes but rules override with dangling ending."""
        raw = "RECIPIENT: mom\nBODY: I went to the\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["coherent"] is False

    def test_body_with_special_characters(self):
        raw = "RECIPIENT: john\nBODY: Hey! How's it going? :)\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["body"] == "Hey! How's it going? :)"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BEHAVIORAL TESTS — _build_send_marker
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildSendMarker:
    def test_marker_format(self):
        marker = _build_send_marker("+15551234567", "Hello there")
        assert marker.startswith("[[CLIENT_TOOL:contacts.sms_send_direct:")
        assert marker.endswith("]]")
        payload = json.loads(marker[len("[[CLIENT_TOOL:contacts.sms_send_direct:"):-2])
        assert payload["phone_number"] == "+15551234567"
        assert payload["body"] == "Hello there"

    def test_marker_escapes_special_chars(self):
        marker = _build_send_marker("+1555", 'He said "hi" & bye')
        payload = json.loads(marker[len("[[CLIENT_TOOL:contacts.sms_send_direct:"):-2])
        assert payload["body"] == 'He said "hi" & bye'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BEHAVIORAL TESTS — _check_open_draft
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckOpenDraft:
    """Verify the Stage 2 safety-net for open SMS drafts."""

    def _mock_deps(self, pending_action=None, session_id="sess-123"):
        mock_get_active_state = MagicMock(return_value={
            "pending_action": pending_action,
        })
        mock_get_session = MagicMock(return_value=session_id)
        mock_is_confirm = MagicMock(side_effect=lambda p: p.lower().strip() in {"yes", "yeah", "yep", "send it"})
        mock_is_cancel = MagicMock(side_effect=lambda p: p.lower().strip() in {"cancel", "nevermind", "no"})
        mock_is_edit = MagicMock(side_effect=lambda p: p.lower().strip().startswith(("change ", "add ", "make it ")))
        mock_normalize = MagicMock(side_effect=lambda p: p.lower().strip().rstrip(".,!?"))
        cancel_strong = {"cancel", "cancel that", "cancel it", "never mind", "nevermind",
                         "forget it", "drop it", "abort", "scratch that", "stop"}
        return {
            "vault_web.recent_turns": MagicMock(get_active_state=mock_get_active_state),
            "jane_web.jane_v2.pending_action_resolver": MagicMock(
                _is_confirm=mock_is_confirm,
                _is_cancel=mock_is_cancel,
                _is_edit_intent=mock_is_edit,
                _STAGE3_CANCEL_STRONG=cancel_strong,
                _normalize=mock_normalize,
            ),
            "jane_web.session_context": MagicMock(get_current_session_id=mock_get_session),
        }

    def test_no_pending_action_returns_none(self):
        mocks = self._mock_deps(pending_action=None)
        with patch.dict(sys.modules, mocks):
            assert _check_open_draft("yes") is None

    def test_wrong_pending_type_returns_none(self):
        mocks = self._mock_deps(pending_action={"type": "SOMETHING_ELSE"})
        with patch.dict(sys.modules, mocks):
            assert _check_open_draft("yes") is None

    def test_confirm_sends(self):
        pending = {
            "type": "SEND_MESSAGE_DRAFT_OPEN",
            "data": {"draft_id": "draft-abc-123", "query": "wife", "body": "I love you"},
        }
        mocks = self._mock_deps(pending_action=pending)
        with patch.dict(sys.modules, mocks):
            result = _check_open_draft("yes")
        assert result is not None
        assert "Sending to wife" in result["text"]
        assert "sms_send" in result["text"]
        assert result["structured"]["pending_action"]["resolution"] == "sent"
        assert result["structured"]["safety"]["side_effectful"] is True

    def test_strong_cancel(self):
        pending = {
            "type": "SEND_MESSAGE_DRAFT_OPEN",
            "data": {"draft_id": "draft-abc-123", "query": "mom", "body": "Hi"},
        }
        mocks = self._mock_deps(pending_action=pending)
        with patch.dict(sys.modules, mocks):
            result = _check_open_draft("cancel")
        assert result is not None
        assert "cancelled" in result["text"].lower()
        assert result["structured"]["pending_action"]["resolution"] == "cancelled"

    def test_edit_intent_escalates(self):
        pending = {
            "type": "SEND_MESSAGE_DRAFT_OPEN",
            "data": {"draft_id": "draft-abc-123", "query": "dad", "body": "Hi"},
        }
        mocks = self._mock_deps(pending_action=pending)
        with patch.dict(sys.modules, mocks):
            result = _check_open_draft("change it to say hello")
        assert result is None

    def test_no_session_returns_none(self):
        mocks = self._mock_deps(pending_action=None, session_id=None)
        with patch.dict(sys.modules, mocks):
            assert _check_open_draft("yes") is None

    def test_import_failure_returns_none(self):
        with patch.dict(sys.modules, {"vault_web.recent_turns": None}):
            result = _check_open_draft("yes")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 5. BEHAVIORAL TESTS — _extract_via_llm
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractViaLlm:
    """Verify LLM extraction with mocked HTTP calls."""

    @pytest.fixture
    def mock_httpx(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "RECIPIENT: wife\nBODY: I love you\nCOHERENT: yes"
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("jane_web.jane_v2.classes.send_message.handler.httpx.AsyncClient",
                    return_value=mock_client) as mock_cls:
            yield mock_cls, mock_client, mock_response

    def test_successful_extraction(self, mock_httpx):
        _, mock_client, _ = mock_httpx
        result = asyncio.get_event_loop().run_until_complete(
            _extract_via_llm("text my wife I love her", "")
        )
        assert result is not None
        assert result["recipient"] == "wife"
        assert result["body"] == "I love you"
        assert result["coherent"] is True
        mock_client.post.assert_awaited_once()

    def test_llm_returns_wrong_class(self, mock_httpx):
        _, _, mock_response = mock_httpx
        mock_response.json.return_value = {"response": "WRONG_CLASS"}
        result = asyncio.get_event_loop().run_until_complete(
            _extract_via_llm("what's the weather?", "")
        )
        assert result is _WRONG_CLASS_SENTINEL

    def test_llm_failure_returns_none(self):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("jane_web.jane_v2.classes.send_message.handler.httpx.AsyncClient",
                    return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                _extract_via_llm("text wife hello", "")
            )
        assert result is None

    def test_context_block_included_when_present(self, mock_httpx):
        _, mock_client, _ = mock_httpx
        asyncio.get_event_loop().run_until_complete(
            _extract_via_llm("tell her I'm coming", "Jane: Who?\nUser: My wife")
        )
        call_args = mock_client.post.call_args
        prompt_sent = call_args[1]["json"]["prompt"] if "json" in call_args[1] else call_args[0][1]["prompt"]
        assert "Recent conversation:" in prompt_sent

    def test_empty_context_no_block(self, mock_httpx):
        _, mock_client, _ = mock_httpx
        asyncio.get_event_loop().run_until_complete(
            _extract_via_llm("text john hello", "")
        )
        call_args = mock_client.post.call_args
        body = call_args[1].get("json") or call_args[0][1]
        assert "Recent conversation:" not in body["prompt"]

    def test_llm_returns_empty_response(self, mock_httpx):
        _, _, mock_response = mock_httpx
        mock_response.json.return_value = {"response": ""}
        result = asyncio.get_event_loop().run_until_complete(
            _extract_via_llm("text wife", "")
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. BEHAVIORAL TESTS — _handle_resume
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleResume:
    """Verify the confirm-or-revise state machine."""

    @pytest.fixture(autouse=True)
    def mock_agent_skills(self):
        mock_end_phrase = MagicMock()
        mock_end_phrase.is_end = MagicMock(side_effect=lambda p: p.lower().strip() in {
            "stop", "cancel", "nevermind", "forget it", "bye", "goodbye", "end"
        })
        mock_confirmation = MagicMock()
        mock_confirmation.is_yes = MagicMock(side_effect=lambda p: p.lower().strip() in {
            "yes", "yeah", "yep", "sure", "send it", "do it"
        })
        mock_confirmation.is_no = MagicMock(side_effect=lambda p: p.lower().strip() in {
            "no", "nope", "nah"
        })

        mock_utils = MagicMock()
        mock_utils.end_conversation = MagicMock(
            side_effect=lambda text, structured=None: {
                "text": text,
                "conversation_end": True,
                **({"structured": structured} if structured else {}),
            }
        )
        mock_utils.pending_continuation = MagicMock(
            side_effect=lambda **kwargs: {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": kwargs.get("handler_class"),
                "data": {
                    "awaiting": kwargs.get("awaiting"),
                    "question": kwargs.get("question"),
                    "draft": (kwargs.get("data") or {}).get("draft"),
                },
            }
        )

        with patch.dict(sys.modules, {
            "agent_skills": MagicMock(end_phrase=mock_end_phrase, confirmation=mock_confirmation),
            "agent_skills.end_phrase": mock_end_phrase,
            "agent_skills.confirmation": mock_confirmation,
            "agent_skills.private_handler_utils": mock_utils,
        }):
            yield

    def _make_pending(self, awaiting, phone="+15551234567", display="wife", body="I love you"):
        return {
            "handler_class": "send message",
            "data": {
                "awaiting": awaiting,
                "draft": {"phone": phone, "display": display, "body": body},
            },
        }

    def test_confirm_yes_sends(self):
        pending = self._make_pending("send_confirmation")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("yes", pending)
        )
        assert result["conversation_end"] is True
        assert "Done" in result["text"]
        assert "sms_send_direct" in result["text"]
        assert result["structured"]["safety"]["side_effectful"] is True

    def test_confirm_yes_but_missing_phone_abandons(self):
        pending = self._make_pending("send_confirmation", phone="")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("yes", pending)
        )
        assert result.get("abandon_pending") is True
        assert result.get("force_stage3") is True

    def test_confirm_yes_but_missing_body_abandons(self):
        pending = self._make_pending("send_confirmation", body="")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("yes", pending)
        )
        assert result.get("abandon_pending") is True

    def test_confirm_no_asks_for_revision(self):
        pending = self._make_pending("send_confirmation")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("no", pending)
        )
        assert "updated message" in result["text"].lower()
        pa = result["structured"]["pending_action"]
        assert pa["data"]["awaiting"] == "revised_body"

    def test_confirm_end_phrase_cancels(self):
        pending = self._make_pending("send_confirmation")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("cancel", pending)
        )
        assert result["conversation_end"] is True
        assert result["text"] == "Ok."

    def test_confirm_unrecognized_escalates(self):
        pending = self._make_pending("send_confirmation")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("what's the weather like?", pending)
        )
        assert result.get("abandon_pending") is True
        assert result.get("force_stage3") is True

    def test_revised_body_end_phrase(self):
        pending = self._make_pending("revised_body")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("nevermind", pending)
        )
        assert result["conversation_end"] is True

    def test_revised_body_empty_abandons(self):
        pending = self._make_pending("revised_body")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("", pending)
        )
        assert result.get("abandon_pending") is True

    def test_revised_body_new_message_loops_back(self):
        pending = self._make_pending("revised_body")
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("I miss you so much", pending)
        )
        assert "Should I send it?" in result["text"]
        assert "I miss you so much" in result["text"]
        pa = result["structured"]["pending_action"]
        assert pa["data"]["awaiting"] == "send_confirmation"
        assert pa["data"]["draft"]["body"] == "I miss you so much"

    def test_unknown_awaiting_abandons(self):
        pending = {
            "handler_class": "send message",
            "data": {"awaiting": "something_unexpected", "draft": {}},
        }
        result = asyncio.get_event_loop().run_until_complete(
            _handle_resume("hello", pending)
        )
        assert result.get("abandon_pending") is True


# ═══════════════════════════════════════════════════════════════════════════════
# 7. BEHAVIORAL TESTS — handle (main entry point)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandle:
    """Verify the main handle() orchestration logic."""

    @pytest.fixture(autouse=True)
    def mock_all_deps(self):
        mock_resolve = MagicMock(return_value={
            "phone_number": "+15551234567",
            "display_name": "Kathia",
            "source": "alias",
        })
        mock_add_alias = MagicMock(return_value=True)
        mock_normalize_name = MagicMock(side_effect=lambda n: n.lower().strip())

        mock_sms = MagicMock(
            resolve_recipient=mock_resolve,
            add_alias=mock_add_alias,
            _normalize_name=mock_normalize_name,
        )
        self._mock_resolve = mock_resolve
        self._mock_sms = mock_sms

        mock_utils = MagicMock()
        mock_utils.pending_continuation = MagicMock(
            side_effect=lambda **kwargs: {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": kwargs.get("handler_class"),
                "data": {
                    "awaiting": kwargs.get("awaiting"),
                    "question": kwargs.get("question"),
                    "draft": (kwargs.get("data") or {}).get("draft"),
                },
            }
        )

        with patch.dict(sys.modules, {
            "agent_skills.sms_helpers": mock_sms,
            "agent_skills.private_handler_utils": mock_utils,
        }):
            with patch(
                "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
                return_value=None,
            ):
                with patch(
                    "jane_web.jane_v2.classes.send_message.handler._extract_via_llm",
                    new_callable=AsyncMock,
                ) as mock_llm:
                    self._mock_llm = mock_llm
                    yield

    def test_params_fast_path_coherent(self):
        params = {"recipient": "wife", "body": "I love you", "intent_kind": "send"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("text wife I love her", params=params)
        )
        assert result is not None
        assert result.get("conversation_end") is True
        assert "sms_send_direct" in result["text"]
        assert result["structured"]["entities"]["recipient"] == "Kathia"

    def test_params_intent_ask_escalates(self):
        params = {"recipient": "wife", "body": "are you ok?", "intent_kind": "ask"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("ask wife if she's ok", params=params)
        )
        assert result is None

    def test_params_no_recipient_escalates(self):
        params = {"recipient": "", "body": "hello", "intent_kind": "send"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("text someone hello", params=params)
        )
        assert result is None

    def test_params_no_body_escalates(self):
        params = {"recipient": "wife", "body": "", "intent_kind": "send"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("text wife", params=params)
        )
        assert result is None

    def test_params_incoherent_body_triggers_confirm(self):
        params = {"recipient": "wife", "body": "I was going to the", "intent_kind": "send"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("text wife I was going to the", params=params)
        )
        assert result is not None
        assert "Should I send it?" in result["text"]
        assert result.get("conversation_end") is not True

    def test_llm_extraction_path(self):
        self._mock_llm.return_value = {
            "recipient": "mom",
            "body": "I'm on my way",
            "coherent": True,
        }
        self._mock_resolve.return_value = {
            "phone_number": "+15559876543",
            "display_name": "Mom",
            "source": "alias",
        }
        result = asyncio.get_event_loop().run_until_complete(
            handle("let mom know I'm on my way")
        )
        assert result is not None
        assert result["conversation_end"] is True
        assert "sms_send_direct" in result["text"]

    def test_llm_wrong_class(self):
        self._mock_llm.return_value = _WRONG_CLASS_SENTINEL
        result = asyncio.get_event_loop().run_until_complete(
            handle("what's the weather like?")
        )
        assert result is _WRONG_CLASS_SENTINEL

    def test_llm_extraction_fails(self):
        self._mock_llm.return_value = None
        result = asyncio.get_event_loop().run_until_complete(
            handle("text someone something")
        )
        assert result is None

    def test_unresolved_recipient_escalates(self):
        self._mock_resolve.return_value = None
        params = {"recipient": "unknown_person", "body": "hello", "intent_kind": "send"}
        result = asyncio.get_event_loop().run_until_complete(
            handle("text unknown_person hello", params=params)
        )
        assert result is None

    def test_resume_path_dispatches(self):
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._handle_resume",
            new_callable=AsyncMock,
            return_value={"text": "resumed", "conversation_end": True},
        ) as mock_resume:
            pending = {"handler_class": "send message", "data": {"awaiting": "send_confirmation"}}
            result = asyncio.get_event_loop().run_until_complete(
                handle("yes", pending=pending)
            )
            mock_resume.assert_awaited_once()
            assert result["text"] == "resumed"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Boundary conditions and degenerate inputs."""

    def test_is_coherent_very_long_body(self):
        body = "word " * 5000 + "done"
        assert _is_coherent(body) is True

    def test_is_coherent_very_long_body_dangling(self):
        body = "word " * 5000 + "the"
        assert _is_coherent(body) is False

    def test_parse_extraction_very_long_body(self):
        long_body = "a " * 10000
        raw = f"RECIPIENT: john\nBODY: {long_body.strip()}\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result is not None
        assert result["recipient"] == "john"

    def test_parse_extraction_recipient_with_special_chars(self):
        raw = "RECIPIENT: María José\nBODY: Hola\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["recipient"] == "María José"

    def test_parse_extraction_body_with_newline_embedded(self):
        """Only the first BODY: line is captured; subsequent lines are ignored."""
        raw = "RECIPIENT: john\nBODY: Line one\nExtra line\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["body"] == "Line one"

    def test_is_coherent_single_dangling_word(self):
        assert _is_coherent("the") is False

    def test_is_coherent_single_filler_word(self):
        assert _is_coherent("um") is False

    def test_is_coherent_punctuation_only(self):
        assert _is_coherent("...") is True

    def test_build_send_marker_empty_body(self):
        marker = _build_send_marker("+1555", "")
        payload = json.loads(marker.split("sms_send_direct:")[1].rstrip("]"))
        assert payload["body"] == ""

    def test_build_send_marker_unicode_body(self):
        marker = _build_send_marker("+1555", "I love you 💕")
        payload = json.loads(marker.split("sms_send_direct:")[1].rstrip("]"))
        assert payload["body"] == "I love you 💕"

    def test_parse_extraction_multiple_recipient_lines(self):
        """Last RECIPIENT line wins (parser overwrites on each match)."""
        raw = "RECIPIENT: alice\nRECIPIENT: bob\nBODY: Hi\nCOHERENT: yes"
        result = _parse_extraction(raw)
        assert result["recipient"] == "bob"

    def test_handle_empty_prompt(self):
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch(
                "jane_web.jane_v2.classes.send_message.handler._extract_via_llm",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = asyncio.get_event_loop().run_until_complete(
                    handle("", context="")
                )
                assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 9. STRUCTURAL INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralInvariants:
    """High-leverage checks on lookup tables, destructive-op guards, and
    handler dispatch shape."""

    # ── Lookup table invariants ──────────────────────────────────────────

    def test_dangling_endings_all_lowercase(self):
        for word in _DANGLING_ENDINGS:
            assert word == word.lower(), f"_DANGLING_ENDINGS entry '{word}' is not lowercase"

    def test_filler_words_all_lowercase(self):
        for word in _FILLER_WORDS:
            assert word == word.lower(), f"_FILLER_WORDS entry '{word}' is not lowercase"

    def test_device_commands_all_lowercase(self):
        for cmd in _DEVICE_COMMANDS:
            assert cmd == cmd.lower(), f"_DEVICE_COMMANDS entry '{cmd}' is not lowercase"

    def test_dangling_endings_no_punctuation(self):
        for word in _DANGLING_ENDINGS:
            assert word == word.strip(".,!?"), f"_DANGLING_ENDINGS entry '{word}' has trailing punctuation"

    def test_filler_words_no_overlap_with_dangling(self):
        overlap = _FILLER_WORDS & _DANGLING_ENDINGS
        assert not overlap, f"Unexpected overlap between filler and dangling: {overlap}"

    def test_every_dangling_word_is_reachable(self):
        for word in _DANGLING_ENDINGS:
            body = f"I was going to see {word}"
            assert _is_coherent(body) is False, (
                f"_DANGLING_ENDINGS entry '{word}' does not trigger incoherence"
            )

    def test_every_filler_word_is_reachable(self):
        for word in _FILLER_WORDS:
            body = f"I {word} think so"
            assert _is_coherent(body) is False, (
                f"_FILLER_WORDS entry '{word}' does not trigger incoherence"
            )

    def test_every_device_command_is_reachable(self):
        for cmd in _DEVICE_COMMANDS:
            body = f"I'm coming home {cmd} set a timer"
            assert _is_coherent(body) is False, (
                f"_DEVICE_COMMANDS entry '{cmd}' does not trigger incoherence"
            )

    # ── Destructive operation guards ─────────────────────────────────────

    def test_fast_path_requires_coherent_true(self):
        """sms_send_direct (fast path) must never fire when coherent=False."""
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=MagicMock(return_value={
                        "phone_number": "+15551234567",
                        "display_name": "Kathia",
                        "source": "alias",
                    }),
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(side_effect=lambda n: n.lower()),
                ),
                "agent_skills.private_handler_utils": MagicMock(
                    pending_continuation=MagicMock(
                        side_effect=lambda **kw: {"type": "STAGE2_FOLLOWUP", "data": kw}
                    ),
                ),
            }):
                params = {"recipient": "wife", "body": "I was going to the", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text wife I was going to the", params=params)
                )
                assert result is not None
                assert "sms_send_direct" not in result.get("text", ""), (
                    "CRITICAL: sms_send_direct fired on incoherent body"
                )
                assert result.get("conversation_end") is not True, (
                    "CRITICAL: conversation ended without confirmation on incoherent body"
                )

    def test_fast_path_requires_resolved_recipient(self):
        """sms_send_direct must not fire when recipient is unresolved."""
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=MagicMock(return_value=None),
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(),
                ),
            }):
                params = {"recipient": "some_stranger", "body": "hello", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text some_stranger hello", params=params)
                )
                assert result is None, (
                    "CRITICAL: handler did not escalate for unresolved recipient"
                )

    def test_fast_path_requires_non_empty_body(self):
        """sms_send_direct must not fire when body is missing."""
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=MagicMock(return_value={
                        "phone_number": "+1555",
                        "display_name": "Wife",
                        "source": "alias",
                    }),
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(),
                ),
            }):
                params = {"recipient": "wife", "body": "", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text wife", params=params)
                )
                assert result is None, (
                    "CRITICAL: handler did not escalate for missing body"
                )

    def test_confirm_yes_with_incomplete_draft_does_not_send(self):
        """If resume('yes') has an empty phone or body, it must NOT send."""
        mock_end_phrase = MagicMock()
        mock_end_phrase.is_end = MagicMock(return_value=False)
        mock_confirmation = MagicMock()
        mock_confirmation.is_yes = MagicMock(return_value=True)
        mock_confirmation.is_no = MagicMock(return_value=False)

        with patch.dict(sys.modules, {
            "agent_skills": MagicMock(end_phrase=mock_end_phrase, confirmation=mock_confirmation),
            "agent_skills.end_phrase": mock_end_phrase,
            "agent_skills.confirmation": mock_confirmation,
            "agent_skills.private_handler_utils": MagicMock(
                end_conversation=MagicMock(),
                pending_continuation=MagicMock(),
            ),
        }):
            pending = {
                "handler_class": "send message",
                "data": {
                    "awaiting": "send_confirmation",
                    "draft": {"phone": "", "display": "wife", "body": ""},
                },
            }
            result = asyncio.get_event_loop().run_until_complete(
                _handle_resume("yes", pending)
            )
            assert result.get("abandon_pending") is True, (
                "CRITICAL: handler attempted to send with incomplete draft"
            )
            assert "sms_send_direct" not in result.get("text", "")

    # ── Handler return shape invariants ──────────────────────────────────

    def test_fast_path_return_has_required_keys(self):
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=MagicMock(return_value={
                        "phone_number": "+15551234567",
                        "display_name": "Kathia",
                        "source": "alias",
                    }),
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(side_effect=lambda n: n.lower()),
                ),
            }):
                params = {"recipient": "wife", "body": "I love you", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text wife I love her", params=params)
                )
                assert "text" in result, "Fast-path result missing 'text' key"
                assert "conversation_end" in result, "Fast-path result missing 'conversation_end'"
                assert "structured" in result, "Fast-path result missing 'structured'"
                assert "entities" in result["structured"]
                assert "safety" in result["structured"]

    def test_confirm_path_return_has_pending_action(self):
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=MagicMock(return_value={
                        "phone_number": "+15551234567",
                        "display_name": "Kathia",
                        "source": "alias",
                    }),
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(side_effect=lambda n: n.lower()),
                ),
                "agent_skills.private_handler_utils": MagicMock(
                    pending_continuation=MagicMock(
                        side_effect=lambda **kw: {"type": "STAGE2_FOLLOWUP", "data": kw}
                    ),
                ),
            }):
                params = {"recipient": "wife", "body": "I um love you", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text wife I um love her", params=params)
                )
                assert "text" in result
                assert "structured" in result
                assert "pending_action" in result["structured"]

    def test_wrong_class_sentinel_is_dict_with_key(self):
        assert isinstance(_WRONG_CLASS_SENTINEL, dict)
        assert _WRONG_CLASS_SENTINEL.get("wrong_class") is True
        assert len(_WRONG_CLASS_SENTINEL) == 1

    # ── Coherence as gate for destructive action ─────────────────────────

    def test_coherent_true_is_only_fast_path_gate(self):
        """Rule-based coherence must override LLM COHERENT=yes when filler detected."""
        assert _is_coherent("Tell uh him I said hello") is False
        raw = "RECIPIENT: john\nBODY: Tell uh him I said hello\nCOHERENT: yes"
        parsed = _parse_extraction(raw)
        assert parsed["coherent"] is False

    def test_coherent_true_overrides_llm_coherent_no(self):
        """If LLM says COHERENT=no, coherent must be False regardless of rules."""
        raw = "RECIPIENT: john\nBODY: Hello there friend\nCOHERENT: no"
        parsed = _parse_extraction(raw)
        assert parsed["coherent"] is False

    # ── Extract prompt template invariants ───────────────────────────────

    def test_extract_prompt_has_placeholders(self):
        assert "{prompt}" in _EXTRACT_PROMPT
        assert "{context_block}" in _EXTRACT_PROMPT

    def test_extract_prompt_mentions_wrong_class(self):
        assert "WRONG_CLASS" in _EXTRACT_PROMPT

    def test_extract_prompt_mentions_perspective_rewrite(self):
        assert "I love you" in _EXTRACT_PROMPT

    def test_extract_prompt_mentions_none_body(self):
        assert "(none)" in _EXTRACT_PROMPT

    # ── Dangling-word check edge: punctuation stripping ──────────────────

    def test_dangling_word_with_exclamation(self):
        assert _is_coherent("I went to the!") is False

    def test_dangling_word_with_question_mark(self):
        assert _is_coherent("I was thinking about the?") is False

    def test_non_dangling_word_with_punctuation(self):
        assert _is_coherent("I'm going home!") is True

    # ── Filler detection edge: trailing punctuation ──────────────────────

    def test_filler_with_comma(self):
        assert _is_coherent("Well, um, ok") is False

    def test_filler_at_end_of_sentence(self):
        assert _is_coherent("I think so hmm.") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 10. INTEGRATION POINT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegrationPoints:
    """Test boundaries where handler interacts with external systems."""

    def test_resolve_recipient_called_with_extracted_name(self):
        mock_resolve = MagicMock(return_value=None)
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=mock_resolve,
                    add_alias=MagicMock(),
                    _normalize_name=MagicMock(),
                ),
            }):
                params = {"recipient": "Mom", "body": "Hi there", "intent_kind": "send"}
                asyncio.get_event_loop().run_until_complete(
                    handle("text mom hi there", params=params)
                )
                mock_resolve.assert_called_once_with("Mom")

    def test_auto_alias_only_for_contacts_source(self):
        mock_resolve = MagicMock(return_value={
            "phone_number": "+15551234567",
            "display_name": "Kathia",
            "source": "alias",
        })
        mock_add_alias = MagicMock()
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": MagicMock(
                    resolve_recipient=mock_resolve,
                    add_alias=mock_add_alias,
                    _normalize_name=MagicMock(side_effect=lambda n: n.lower()),
                ),
            }):
                params = {"recipient": "wife", "body": "I love you", "intent_kind": "send"}
                asyncio.get_event_loop().run_until_complete(
                    handle("text wife I love her", params=params)
                )
                mock_add_alias.assert_not_called()

    def test_ollama_request_body_shape(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "RECIPIENT: john\nBODY: Hey\nCOHERENT: yes"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("jane_web.jane_v2.classes.send_message.handler.httpx.AsyncClient",
                    return_value=mock_client):
            asyncio.get_event_loop().run_until_complete(
                _extract_via_llm("text john hey", "")
            )

        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1].get("json") or call_kwargs.kwargs.get("json")
        assert body["stream"] is False
        assert body["options"]["temperature"] == 0.0
        assert "num_ctx" in body["options"]
        assert "keep_alive" in body

    def test_sms_helpers_import_failure_escalates(self):
        with patch(
            "jane_web.jane_v2.classes.send_message.handler._check_open_draft",
            return_value=None,
        ):
            with patch.dict(sys.modules, {
                "agent_skills.sms_helpers": None,
            }):
                params = {"recipient": "wife", "body": "hello", "intent_kind": "send"}
                result = asyncio.get_event_loop().run_until_complete(
                    handle("text wife hello", params=params)
                )
                assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
