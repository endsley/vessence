"""Audit tests for jane_web.jane_v2.recent_context.

Spec source: module docstrings.
"""

from __future__ import annotations

import ast
import builtins
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "jane_web" / "jane_v2" / "recent_context.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jane_web.jane_v2 import recent_context as rc


EMPTY_PACKET = {
    "pending_action": None,
    "last_intent": "",
    "last_entities": {},
    "recent_summary": "",
}


@pytest.fixture()
def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture()
def fake_recent_turns(monkeypatch):
    def install(
        *,
        recent=None,
        structured=None,
        state=None,
        recent_side_effect=None,
        structured_side_effect=None,
        state_side_effect=None,
    ):
        pkg = types.ModuleType("vault_web")
        pkg.__path__ = []

        mod = types.ModuleType("vault_web.recent_turns")
        mod.get_recent = MagicMock(
            return_value=[] if recent is None else recent,
            side_effect=recent_side_effect,
        )
        mod.get_recent_structured = MagicMock(
            return_value=[] if structured is None else structured,
            side_effect=structured_side_effect,
        )
        mod.get_active_state = MagicMock(
            return_value={} if state is None else state,
            side_effect=state_side_effect,
        )

        monkeypatch.setitem(sys.modules, "vault_web", pkg)
        monkeypatch.setitem(sys.modules, "vault_web.recent_turns", mod)
        return mod

    return install


def _force_recent_turns_import_failure(monkeypatch) -> None:
    real_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "vault_web.recent_turns":
            raise ImportError("forced missing FIFO module")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)


def _call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()

    def render(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = render(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = render(node.func)
            if name:
                names.add(name)
    return names


def _module_level_dict_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            names.extend(target.id for target in node.targets if isinstance(target, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            names.append(node.target.id)
    return names


class TestConstantsAndPublicShape:
    def test_default_budget_constants_match_docstring_heuristic(self):
        assert rc._CHARS_PER_TOKEN == 4
        assert rc.DEFAULT_MAX_TURNS == 10
        assert rc.DEFAULT_MAX_TOKENS == 600
        assert rc.DEFAULT_MAX_TOKENS * rc._CHARS_PER_TOKEN >= rc.DEFAULT_MAX_TURNS * 190

    def test_public_context_functions_are_callable(self):
        for name in (
            "get_recent_context",
            "get_stage1_context_packet",
            "render_stage2_context",
            "render_stage3_context",
        ):
            assert callable(getattr(rc, name))


class TestCloudSummaryRedaction:
    def test_cloud_safe_record_returns_stored_summary(self):
        assert rc._redact_summary_for_cloud(
            {"summary": "user asked about weather", "privacy": "cloud_ok"}
        ) == "user asked about weather"

    def test_missing_summary_returns_empty_string(self):
        assert rc._redact_summary_for_cloud({"privacy": "cloud_ok"}) == ""
        assert rc._redact_summary_for_cloud({}) == ""

    def test_local_only_summary_is_replaced_with_class_placeholder(self):
        result = rc._redact_summary_for_cloud(
            {
                "privacy": "local_only",
                "intent": "send_message",
                "summary": "secret SMS body",
            }
        )

        assert "private turn" in result
        assert "send_message" in result
        assert "secret SMS body" not in result

    def test_local_only_without_intent_uses_private_class_label(self):
        result = rc._redact_summary_for_cloud(
            {"privacy": "local_only", "summary": "secret"}
        )

        assert "private turn" in result
        assert "class: private" in result
        assert "secret" not in result


class TestGetRecentContextBehavior:
    @pytest.mark.parametrize("session_id", [None, "", 0, False])
    def test_falsey_session_returns_empty_without_fifo_import(
        self, session_id, monkeypatch
    ):
        _force_recent_turns_import_failure(monkeypatch)

        assert rc.get_recent_context(session_id) == ""

    def test_import_failure_returns_empty_and_never_raises(self, monkeypatch):
        _force_recent_turns_import_failure(monkeypatch)

        assert rc.get_recent_context("session-1") == ""

    def test_fifo_read_failure_returns_empty(self, fake_recent_turns):
        fake_recent_turns(recent_side_effect=RuntimeError("db locked"))

        assert rc.get_recent_context("session-1") == ""

    def test_empty_or_none_fifo_history_returns_empty(self, fake_recent_turns):
        fake_recent_turns(recent=[])
        assert rc.get_recent_context("session-1") == ""

        fake_recent_turns(recent=None)
        assert rc.get_recent_context("session-1") == ""

    def test_reads_fifo_with_session_and_turn_limit(self, fake_recent_turns):
        fifo = fake_recent_turns(recent=["turn one"])

        assert rc.get_recent_context("session-1", max_turns=7) == "turn one"
        fifo.get_recent.assert_called_once_with("session-1", n=7)
        fifo.get_recent_structured.assert_not_called()

    def test_formats_oldest_first_and_skips_blank_summaries(self, fake_recent_turns):
        fake_recent_turns(recent=["  turn-1  ", "", " \t ", "turn-2", "turn-3"])

        assert rc.get_recent_context("session-1", max_tokens=10_000) == (
            "turn-1\nturn-2\nturn-3"
        )

    def test_budget_trimming_drops_oldest_and_preserves_newest(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["oldest", "middle", "newest"])

        result = rc.get_recent_context("session-1", max_turns=10, max_tokens=4)

        assert "newest" in result
        assert result.splitlines()[-1] == "newest"
        assert "oldest" not in result

    def test_zero_or_negative_budget_still_keeps_newest_turn(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["old", "new"])

        assert rc.get_recent_context("session-1", max_tokens=0) == "new"
        assert rc.get_recent_context("session-1", max_tokens=-100) == "new"

    def test_very_long_newest_turn_is_preserved_even_over_soft_budget(
        self, fake_recent_turns
    ):
        newest = "newest " + ("x" * 10_000)
        fake_recent_turns(recent=["old turn", newest])

        result = rc.get_recent_context("session-1", max_tokens=1)

        assert result == newest
        assert "old turn" not in result

    def test_redacted_mode_uses_structured_fifo_and_not_plain_fifo(
        self, fake_recent_turns
    ):
        fifo = fake_recent_turns(
            recent=["plain should not be used"],
            structured=[
                {"summary": "public turn", "privacy": "cloud_ok"},
                {
                    "summary": "private SMS body",
                    "privacy": "local_only",
                    "intent": "send_message",
                },
            ],
        )

        result = rc.get_recent_context(
            "session-1", max_turns=5, max_tokens=10_000, redact_local_only=True
        )

        fifo.get_recent.assert_not_called()
        fifo.get_recent_structured.assert_called_once_with("session-1", n=5)
        assert "public turn" in result
        assert "private SMS body" not in result
        assert "private turn" in result
        assert "send_message" in result

    @pytest.mark.xfail(
        reason=(
            "get_recent_context documents 'Never raises', but a malformed FIFO "
            "row that is not a string reaches line.strip()."
        ),
        strict=True,
    )
    def test_malformed_fifo_rows_do_not_break_never_raises_contract(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["valid", None, {"summary": "bad"}])

        assert isinstance(rc.get_recent_context("session-1"), str)

    @pytest.mark.xfail(
        reason=(
            "get_recent_context documents 'Never raises', but malformed "
            "max_tokens is converted outside the read-failure try block."
        ),
        strict=True,
    )
    def test_malformed_token_budget_does_not_break_never_raises_contract(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["valid"])

        assert isinstance(rc.get_recent_context("session-1", max_tokens="bad"), str)


class TestStage1ContextPacket:
    @pytest.mark.parametrize("session_id", [None, "", 0, False])
    def test_falsey_session_returns_empty_packet(self, session_id):
        assert rc.get_stage1_context_packet(session_id) == EMPTY_PACKET

    def test_import_failure_returns_empty_packet(self, monkeypatch):
        _force_recent_turns_import_failure(monkeypatch)

        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET

    def test_active_state_failure_returns_empty_packet(self, fake_recent_turns):
        fake_recent_turns(state_side_effect=RuntimeError("db locked"))

        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET

    def test_reads_active_state_and_returns_documented_packet_shape(
        self, fake_recent_turns
    ):
        state = {
            "pending_action": {"type": "SEND_MESSAGE_CONFIRMATION"},
            "last_intent": "send_message",
            "last_entities": {"recipient": "Kathia"},
            "recent_summaries": ["older", "newest"],
        }
        fifo = fake_recent_turns(state=state)

        packet = rc.get_stage1_context_packet("session-1")

        fifo.get_active_state.assert_called_once_with("session-1")
        assert set(packet) == set(EMPTY_PACKET)
        assert packet["pending_action"] == {"type": "SEND_MESSAGE_CONFIRMATION"}
        assert packet["last_intent"] == "send_message"
        assert packet["last_entities"] == {"recipient": "Kathia"}
        assert packet["recent_summary"] == "newest"

    def test_missing_or_none_state_fields_are_normalized(self, fake_recent_turns):
        fake_recent_turns(state={"last_entities": None, "recent_summaries": None})

        packet = rc.get_stage1_context_packet("session-1")

        assert packet == EMPTY_PACKET
        assert isinstance(packet["last_entities"], dict)
        assert isinstance(packet["last_intent"], str)
        assert isinstance(packet["recent_summary"], str)

    @pytest.mark.xfail(
        reason=(
            "A malformed get_active_state return value is used after the try "
            "block, so state.get raises instead of returning the empty packet."
        ),
        strict=True,
    )
    def test_malformed_active_state_return_does_not_raise(self, fake_recent_turns):
        fake_recent_turns(state_side_effect=lambda session_id: None)

        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET


class TestStateHeaderAndBlockRendering:
    def test_state_header_empty_packet_is_empty(self):
        assert rc._render_state_header({}) == ""

    def test_state_header_includes_intent_and_pending_target(self):
        packet = {
            "last_intent": "send_message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"display_name": "Kathia"},
            },
        }

        result = rc._render_state_header(packet)

        assert result.startswith("[STATE: ")
        assert result.endswith("]")
        assert "last_intent=send_message" in result
        assert "pending=SEND_MESSAGE_CONFIRMATION\u2192Kathia" in result

    def test_state_header_falls_back_to_recipient_and_type_only(self):
        with_recipient = rc._render_state_header(
            {"pending_action": {"type": "X", "data": {"recipient": "Mom"}}}
        )
        without_recipient = rc._render_state_header(
            {"pending_action": {"type": "Y", "data": {}}}
        )

        assert "pending=X\u2192Mom" in with_recipient
        assert "pending=Y" in without_recipient
        assert "\u2192" not in without_recipient

    def test_state_block_has_exact_outer_markers(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)

        result = rc._render_state_block({"last_intent": "weather"})

        assert result.splitlines()[0] == "[CURRENT CONVERSATION STATE]"
        assert result.splitlines()[-1] == "[END CURRENT CONVERSATION STATE]"
        assert "- Last intent: weather." in result

    def test_send_message_confirmation_rendering_variants(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)

        full = rc._render_state_block(
            {
                "last_intent": "send_message",
                "pending_action": {
                    "type": "SEND_MESSAGE_CONFIRMATION",
                    "data": {"display_name": "Kathia", "body": "I love you"},
                },
            }
        )
        target_only = rc._render_state_block(
            {
                "pending_action": {
                    "type": "SEND_MESSAGE_CONFIRMATION",
                    "data": {"recipient": "Mom"},
                }
            }
        )
        no_target = rc._render_state_block(
            {"pending_action": {"type": "SEND_MESSAGE_CONFIRMATION", "data": {}}}
        )

        assert 'awaiting confirmation to SMS Kathia: "I love you"' in full
        assert "User may confirm, revise, or cancel." in full
        assert "awaiting confirmation to SMS Mom" in target_only
        assert "awaiting confirmation to send an SMS" in no_target

    def test_generic_pending_action_and_recent_entities(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)

        pending = rc._render_state_block(
            {
                "last_intent": "calendar",
                "pending_action": {"type": "CALENDAR_CONFIRM", "data": {}},
                "last_entities": {"day": "today"},
            }
        )
        entities = rc._render_state_block(
            {
                "last_intent": "weather",
                "last_entities": {
                    "city": "New York",
                    "unit": "F",
                    "day": "today",
                    "extra": "kept",
                    "fifth": "dropped",
                },
            }
        )

        assert "- Pending action: CALENDAR_CONFIRM." in pending
        assert "Recent entities" not in pending
        assert "Recent entities:" in entities
        assert entities.count("=") == 4
        assert "fifth=dropped" not in entities

    def test_private_class_hides_pending_data_and_entities(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: True)

        pending = rc._render_state_block(
            {
                "last_intent": "send_message",
                "pending_action": {
                    "type": "SEND_MESSAGE_CONFIRMATION",
                    "handler_class": "send_message",
                    "data": {"display_name": "Secret Person", "body": "secret body"},
                },
            }
        )
        entities = rc._render_state_block(
            {
                "last_intent": "send_message",
                "last_entities": {"recipient": "Secret Person"},
            }
        )

        assert "Secret Person" not in pending
        assert "secret body" not in pending
        assert "awaiting confirmation to send an SMS" in pending
        assert "Recent entities" not in entities
        assert "Secret Person" not in entities


class TestPrivateClassLookup:
    def test_false_for_none_empty_and_import_failure(self, monkeypatch):
        assert rc._is_private_class(None) is False
        assert rc._is_private_class("") is False

        real_import = builtins.__import__

        def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "agent_skills.private_handler_utils":
                raise ImportError("forced missing privacy table")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", failing_import)
        assert rc._is_private_class("send_message") is False

    def test_uses_privacy_for_lookup_when_available(self, monkeypatch):
        pkg = types.ModuleType("agent_skills")
        pkg.__path__ = []
        mod = types.ModuleType("agent_skills.private_handler_utils")
        mod.privacy_for = MagicMock(
            side_effect=lambda cls: "local_only" if cls == "send_message" else "cloud_ok"
        )
        monkeypatch.setitem(sys.modules, "agent_skills", pkg)
        monkeypatch.setitem(sys.modules, "agent_skills.private_handler_utils", mod)

        assert rc._is_private_class("send_message") is True
        assert rc._is_private_class("weather") is False
        mod.privacy_for.assert_any_call("send_message")
        mod.privacy_for.assert_any_call("weather")


class TestStage2ContextRenderer:
    @pytest.mark.parametrize("session_id", [None, "", 0, False])
    def test_falsey_session_returns_empty(self, session_id):
        assert rc.render_stage2_context(session_id) == ""

    def test_without_pending_action_returns_prose_only(self, fake_recent_turns):
        fifo = fake_recent_turns(
            recent=["user: hello", "jane: hi"],
            state={"last_intent": "greeting", "pending_action": None},
        )

        result = rc.render_stage2_context("session-1")

        fifo.get_recent.assert_called_once_with("session-1", n=3)
        assert result == "user: hello\njane: hi"
        assert "[STATE:" not in result

    def test_pending_action_adds_compact_state_header(self, fake_recent_turns):
        fake_recent_turns(
            recent=["user: text Kathia I love you"],
            state={
                "last_intent": "send_message",
                "pending_action": {
                    "type": "SEND_MESSAGE_CONFIRMATION",
                    "data": {"display_name": "Kathia"},
                },
            },
        )

        result = rc.render_stage2_context("session-1", max_turns=2)

        assert result.startswith("[STATE: ")
        assert "last_intent=send_message" in result
        assert "pending=SEND_MESSAGE_CONFIRMATION\u2192Kathia" in result
        assert "\n\nuser: text Kathia I love you" in result

    def test_pending_action_without_prose_returns_header_only(self, fake_recent_turns):
        fake_recent_turns(
            recent=[],
            state={
                "last_intent": "send_message",
                "pending_action": {"type": "SEND_MESSAGE_CONFIRMATION", "data": {}},
            },
        )

        result = rc.render_stage2_context("session-1")

        assert result.startswith("[STATE: ")
        assert "\n" not in result


class TestStage3ContextRenderer:
    @pytest.mark.parametrize("session_id", [None, "", 0, False])
    def test_falsey_session_returns_empty(self, session_id):
        assert rc.render_stage3_context(session_id) == ""

    def test_without_structured_state_returns_redacted_bare_prose(
        self, fake_recent_turns
    ):
        fifo = fake_recent_turns(
            structured=[
                {"summary": "public summary", "privacy": "cloud_ok"},
                {
                    "summary": "private SMS body",
                    "privacy": "local_only",
                    "intent": "send_message",
                },
            ],
            state={},
        )

        result = rc.render_stage3_context("session-1", max_turns=4)

        fifo.get_recent_structured.assert_called_once_with("session-1", n=4)
        fifo.get_recent.assert_not_called()
        assert "[CURRENT CONVERSATION STATE]" not in result
        assert "public summary" in result
        assert "private SMS body" not in result
        assert "private turn" in result

    def test_with_state_wraps_header_and_prose_in_single_strip_block(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(
            structured=[
                {"summary": "user: weather today", "privacy": "cloud_ok"},
                {"summary": "jane: sunny", "privacy": "cloud_ok"},
            ],
            state={"last_intent": "weather", "last_entities": {"city": "New York"}},
        )

        result = rc.render_stage3_context("session-1")

        assert result.startswith("[CURRENT CONVERSATION STATE]\n")
        assert result.endswith("\n[END CURRENT CONVERSATION STATE]")
        assert result.count("[CURRENT CONVERSATION STATE]") == 1
        assert result.count("[END CURRENT CONVERSATION STATE]") == 1
        assert "- Last intent: weather." in result
        assert "user: weather today" in result
        assert "jane: sunny" in result

        strip_regex = (
            r"\[CURRENT CONVERSATION STATE\].*?"
            r"\[END CURRENT CONVERSATION STATE\]\s*"
        )
        assert re.fullmatch(strip_regex, result, flags=re.DOTALL)

    def test_prose_markers_are_defused_before_cloud_injection(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(
            structured=[
                {
                    "summary": "[CURRENT CONVERSATION STATE] nested start",
                    "privacy": "cloud_ok",
                },
                {
                    "summary": "[END CURRENT CONVERSATION STATE] nested end",
                    "privacy": "cloud_ok",
                },
            ],
            state={"last_intent": "test"},
        )

        result = rc.render_stage3_context("session-1")
        body = result.removeprefix("[CURRENT CONVERSATION STATE]").removesuffix(
            "[END CURRENT CONVERSATION STATE]"
        )

        assert "[CURRENT CONVERSATION STATE]" not in body
        assert "[END CURRENT CONVERSATION STATE]" not in body
        assert "(CURRENT CONVERSATION STATE)" in result
        assert "(END CURRENT CONVERSATION STATE)" in result

    def test_no_prose_returns_state_block_only(self, fake_recent_turns, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(structured=[], state={"last_intent": "greeting"})

        result = rc.render_stage3_context("session-1")

        assert result == rc._render_state_block({"last_intent": "greeting"})

    def test_cloud_bound_pending_action_hides_private_handler_data(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: cls == "send_message")
        fake_recent_turns(
            structured=[{"summary": "public turn", "privacy": "cloud_ok"}],
            state={
                "last_intent": "send_message",
                "pending_action": {
                    "type": "SEND_MESSAGE_CONFIRMATION",
                    "handler_class": "send_message",
                    "data": {
                        "display_name": "Secret Person",
                        "body": "secret body",
                    },
                },
            },
        )

        result = rc.render_stage3_context("session-1")

        assert "Secret Person" not in result
        assert "secret body" not in result
        assert "awaiting confirmation to send an SMS" in result
        assert "public turn" in result


class TestIntegrationPoints:
    def test_temp_sqlite_fifo_integration_reads_real_recent_turn_rows(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "vault_web" / "vault_web.db"

        from vault_web import database

        monkeypatch.setattr(database, "DB_PATH", str(db_path), raising=False)
        database.init_db()

        from vault_web import recent_turns

        session_id = "audit-real-sqlite"
        recent_turns.clear(session_id)
        recent_turns.add_structured(
            session_id,
            {
                "summary": "user: public weather question",
                "privacy": "cloud_ok",
                "intent": "weather",
            },
        )
        recent_turns.add_structured(
            session_id,
            {
                "summary": "user: private SMS body",
                "privacy": "local_only",
                "intent": "send_message",
            },
        )

        plain = rc.get_recent_context(session_id, max_turns=5, max_tokens=10_000)
        redacted = rc.get_recent_context(
            session_id, max_turns=5, max_tokens=10_000, redact_local_only=True
        )

        assert plain.splitlines() == [
            "user: public weather question",
            "user: private SMS body",
        ]
        assert "user: public weather question" in redacted
        assert "user: private SMS body" not in redacted
        assert "private turn" in redacted
        assert "send_message" in redacted

    def test_module_has_no_llm_or_network_integration_calls(self, module_ast):
        forbidden_import_roots = {
            "anthropic",
            "google",
            "httpx",
            "ollama",
            "openai",
            "requests",
        }
        imported_roots: set[str] = set()
        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        forbidden_calls = {
            "generate",
            "generate_content",
            "chat",
            "complete",
            "completions",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
        }

        assert imported_roots.isdisjoint(forbidden_import_roots)
        assert _call_names(module_ast).isdisjoint(forbidden_calls)


class TestStructuralInvariants:
    def test_no_module_level_mapping_or_registry_requires_reachability_tests(
        self, module_ast
    ):
        assert _module_level_dict_names(module_ast) == []

    def test_no_destructive_or_irreversible_operations_exist(self, module_ast):
        destructive_names = {
            "delete",
            "execute",
            "executemany",
            "clear",
            "unlink",
            "remove",
            "rmtree",
            "send",
            "send_message",
            "sms_send",
            "sms_send_direct",
            "end_conversation",
        }
        function_names = {
            node.name
            for node in ast.walk(module_ast)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        call_leaf_names = {name.rsplit(".", 1)[-1] for name in _call_names(module_ast)}

        assert function_names.isdisjoint(destructive_names)
        assert call_leaf_names.isdisjoint(destructive_names)

    def test_no_class_registry_or_handler_dispatch_exists(self, module_ast):
        forbidden_function_names = {"dispatch", "handle", "handler", "route"}
        forbidden_calls = {
            "class_registry.get_registry",
            "get_registry",
            "dispatch",
            "handler",
            "handle",
        }
        function_names = {
            node.name
            for node in ast.walk(module_ast)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        assert function_names.isdisjoint(forbidden_function_names)
        assert _call_names(module_ast).isdisjoint(forbidden_calls)

    def test_stage3_renderer_has_required_strip_markers_in_source(
        self, module_source
    ):
        assert "[CURRENT CONVERSATION STATE]" in module_source
        assert "[END CURRENT CONVERSATION STATE]" in module_source
        assert "redact_local_only=True" in module_source

    def test_public_renderers_return_documented_shapes(self, fake_recent_turns):
        fake_recent_turns(
            recent=["turn"],
            structured=[{"summary": "turn", "privacy": "cloud_ok"}],
            state={
                "last_intent": "greeting",
                "pending_action": None,
                "last_entities": {},
                "recent_summaries": ["turn"],
            },
        )

        assert isinstance(rc.get_recent_context("session-1"), str)
        assert isinstance(rc.render_stage2_context("session-1"), str)
        assert isinstance(rc.render_stage3_context("session-1"), str)

        packet = rc.get_stage1_context_packet("session-1")
        assert isinstance(packet, dict)
        assert set(packet) == set(EMPTY_PACKET)
