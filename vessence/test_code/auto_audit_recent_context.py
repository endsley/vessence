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


# ─── Constants & public API shape ────────────────────────────────────────


class TestConstantsAndPublicShape:
    def test_default_budget_constants_match_docstring_heuristic(self):
        assert rc._CHARS_PER_TOKEN == 4
        assert rc.DEFAULT_MAX_TURNS == 10
        assert rc.DEFAULT_MAX_TOKENS == 600
        # 10 turns × ~190 chars/summary should fit within the budget
        assert rc.DEFAULT_MAX_TOKENS * rc._CHARS_PER_TOKEN >= rc.DEFAULT_MAX_TURNS * 190

    def test_public_context_functions_are_callable(self):
        for name in (
            "get_recent_context",
            "get_stage1_context_packet",
            "render_stage2_context",
            "render_stage3_context",
        ):
            assert callable(getattr(rc, name))


# ─── _redact_summary_for_cloud ───────────────────────────────────────────


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

    def test_privacy_none_is_not_local_only(self):
        result = rc._redact_summary_for_cloud(
            {"privacy": None, "summary": "visible"}
        )
        assert result == "visible"

    def test_empty_intent_falls_back_to_private_label(self):
        result = rc._redact_summary_for_cloud(
            {"privacy": "local_only", "intent": "", "summary": "secret"}
        )
        assert "class: private" in result

    def test_summary_none_returns_empty_string(self):
        assert rc._redact_summary_for_cloud({"summary": None}) == ""


# ─── _recent_context_lines_within_budget (direct unit tests) ─────────────


class TestBudgetTrimmer:
    def test_empty_list_returns_empty(self):
        assert rc._recent_context_lines_within_budget([], 1000) == []

    def test_all_whitespace_entries_are_dropped(self):
        assert rc._recent_context_lines_within_budget(["  ", "\t", "\n", ""], 1000) == []

    def test_non_string_entries_are_skipped(self):
        result = rc._recent_context_lines_within_budget(
            ["valid", None, 42, {"key": "val"}, "also valid"], 10000
        )
        assert result == ["valid", "also valid"]

    def test_oldest_first_ordering(self):
        result = rc._recent_context_lines_within_budget(
            ["oldest", "middle", "newest"], 10000
        )
        assert result == ["oldest", "middle", "newest"]

    def test_budget_trims_oldest_first(self):
        # "newest" is 6 chars + 1 newline = 7. Budget of 10 chars should keep
        # "newest" and maybe "middle" (6+1=7, total 14 > 10) — so only newest.
        result = rc._recent_context_lines_within_budget(
            ["oldest", "middle", "newest"], 10
        )
        assert result[-1] == "newest"
        assert "oldest" not in result

    def test_first_entry_always_kept_even_if_over_budget(self):
        # When kept is empty, the entry is always appended regardless of budget
        huge = "x" * 5000
        result = rc._recent_context_lines_within_budget([huge], 10)
        assert result == [huge]

    def test_newest_entry_always_kept_even_if_over_budget(self):
        huge = "x" * 5000
        result = rc._recent_context_lines_within_budget(["old", huge], 10)
        assert result == [huge]
        assert "old" not in result

    def test_exact_budget_boundary(self):
        # "abc" = 3 chars + 1 newline = 4. Two entries = 8.
        result = rc._recent_context_lines_within_budget(["abc", "def"], 8)
        assert result == ["abc", "def"]

    def test_one_char_over_budget_drops_oldest(self):
        # "abc" costs 4, "def" costs 4. Budget 7 means second entry would push
        # to 8 > 7, but since kept is non-empty the break fires.
        result = rc._recent_context_lines_within_budget(["abc", "def"], 7)
        assert result == ["def"]

    def test_strips_whitespace_from_entries(self):
        result = rc._recent_context_lines_within_budget(
            ["  padded  ", "  trimmed  "], 10000
        )
        assert result == ["padded", "trimmed"]

    def test_zero_budget_keeps_newest_only(self):
        result = rc._recent_context_lines_within_budget(
            ["old", "new"], 0
        )
        assert result == ["new"]

    def test_many_turns_budget_preserves_newest_tail(self):
        turns = [f"turn-{i:03d}" for i in range(100)]
        # Each turn is ~8 chars + 1 = 9. Budget of 50 fits ~5 turns.
        result = rc._recent_context_lines_within_budget(turns, 50)
        assert result[-1] == "turn-099"
        assert len(result) <= 6


# ─── get_recent_context ──────────────────────────────────────────────────


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

    def test_empty_fifo_history_returns_empty(self, fake_recent_turns):
        fake_recent_turns(recent=[])
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

    def test_malformed_fifo_rows_do_not_break_never_raises_contract(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["valid", None, {"summary": "bad"}, 42])
        result = rc.get_recent_context("session-1")
        assert isinstance(result, str)
        assert "valid" in result

    def test_malformed_token_budget_does_not_break_never_raises_contract(
        self, fake_recent_turns
    ):
        fake_recent_turns(recent=["valid"])
        assert isinstance(rc.get_recent_context("session-1", max_tokens="bad"), str)

    def test_float_token_budget_is_accepted(self, fake_recent_turns):
        fake_recent_turns(recent=["turn-a", "turn-b"])
        result = rc.get_recent_context("session-1", max_tokens=600.5)
        assert isinstance(result, str)
        assert "turn-b" in result

    def test_structured_fifo_read_failure_returns_empty(self, fake_recent_turns):
        fake_recent_turns(structured_side_effect=RuntimeError("db locked"))
        result = rc.get_recent_context("session-1", redact_local_only=True)
        assert result == ""

    def test_single_turn_always_returned(self, fake_recent_turns):
        fake_recent_turns(recent=["only turn"])
        assert rc.get_recent_context("session-1", max_tokens=1) == "only turn"

    def test_default_arguments_produce_sensible_result(self, fake_recent_turns):
        turns = [f"summary of turn {i}" for i in range(10)]
        fake_recent_turns(recent=turns)
        result = rc.get_recent_context("session-1")
        assert isinstance(result, str)
        assert len(result) > 0
        lines = result.splitlines()
        assert lines[-1] == turns[-1]


# ─── get_stage1_context_packet ───────────────────────────────────────────


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

    def test_malformed_active_state_return_does_not_raise(self, fake_recent_turns):
        fake_recent_turns(state_side_effect=lambda session_id: None)
        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET

    def test_active_state_returns_list_is_treated_as_non_dict(self, fake_recent_turns):
        fake_recent_turns(state_side_effect=lambda session_id: ["not", "a", "dict"])
        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET

    def test_active_state_returns_string_is_treated_as_non_dict(self, fake_recent_turns):
        fake_recent_turns(state_side_effect=lambda session_id: "not a dict")
        assert rc.get_stage1_context_packet("session-1") == EMPTY_PACKET

    def test_empty_summaries_list_yields_empty_recent_summary(self, fake_recent_turns):
        fake_recent_turns(state={"recent_summaries": []})
        packet = rc.get_stage1_context_packet("session-1")
        assert packet["recent_summary"] == ""

    def test_single_summary_is_returned(self, fake_recent_turns):
        fake_recent_turns(state={"recent_summaries": ["the only one"]})
        packet = rc.get_stage1_context_packet("session-1")
        assert packet["recent_summary"] == "the only one"

    def test_packet_always_has_exactly_four_keys(self, fake_recent_turns):
        fake_recent_turns(state={
            "pending_action": {"type": "X"},
            "last_intent": "test",
            "last_entities": {"a": 1, "b": 2},
            "recent_summaries": ["s"],
            "extra_key": "should not appear",
        })
        packet = rc.get_stage1_context_packet("session-1")
        assert set(packet.keys()) == {"pending_action", "last_intent", "last_entities", "recent_summary"}


# ─── _render_state_header (Stage 2) ─────────────────────────────────────


class TestStateHeaderRendering:
    def test_empty_packet_is_empty_string(self):
        assert rc._render_state_header({}) == ""

    def test_intent_only(self):
        result = rc._render_state_header({"last_intent": "weather"})
        assert result == "[STATE: last_intent=weather]"

    def test_pending_only_with_display_name(self):
        result = rc._render_state_header({
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"display_name": "Kathia"},
            }
        })
        assert "pending=SEND_MESSAGE_CONFIRMATION→Kathia" in result
        assert result.startswith("[STATE: ")
        assert result.endswith("]")

    def test_pending_falls_back_to_recipient_key(self):
        result = rc._render_state_header({
            "pending_action": {"type": "X", "data": {"recipient": "Mom"}}
        })
        assert "pending=X→Mom" in result

    def test_pending_without_target_shows_type_only(self):
        result = rc._render_state_header({
            "pending_action": {"type": "Y", "data": {}}
        })
        assert "pending=Y" in result
        assert "→" not in result

    def test_intent_and_pending_both_present(self):
        result = rc._render_state_header({
            "last_intent": "send_message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"display_name": "Kathia"},
            },
        })
        assert "last_intent=send_message" in result
        assert "pending=SEND_MESSAGE_CONFIRMATION→Kathia" in result

    def test_pending_with_no_data_key(self):
        result = rc._render_state_header({
            "pending_action": {"type": "UNKNOWN"}
        })
        assert "pending=UNKNOWN" in result

    def test_display_name_preferred_over_recipient(self):
        result = rc._render_state_header({
            "pending_action": {
                "type": "X",
                "data": {"display_name": "Preferred", "recipient": "Fallback"},
            }
        })
        assert "Preferred" in result
        assert "Fallback" not in result


# ─── _render_state_block (Stage 3) ──────────────────────────────────────


class TestStateBlockRendering:
    def test_state_block_has_exact_outer_markers(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({"last_intent": "weather"})
        assert result.splitlines()[0] == "[CURRENT CONVERSATION STATE]"
        assert result.splitlines()[-1] == "[END CURRENT CONVERSATION STATE]"
        assert "- Last intent: weather." in result

    def test_send_message_confirmation_full(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "last_intent": "send_message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"display_name": "Kathia", "body": "I love you"},
            },
        })
        assert 'awaiting confirmation to SMS Kathia: "I love you"' in result
        assert "User may confirm, revise, or cancel." in result

    def test_send_message_confirmation_target_only(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"recipient": "Mom"},
            }
        })
        assert "awaiting confirmation to SMS Mom" in result

    def test_send_message_confirmation_no_target(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "pending_action": {"type": "SEND_MESSAGE_CONFIRMATION", "data": {}}
        })
        assert "awaiting confirmation to send an SMS" in result

    def test_message_body_fallback_key(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "data": {"display_name": "Bob", "message_body": "hey there"},
            },
        })
        assert '"hey there"' in result
        assert "Bob" in result

    def test_generic_pending_action(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "last_intent": "calendar",
            "pending_action": {"type": "CALENDAR_CONFIRM", "data": {}},
        })
        assert "- Pending action: CALENDAR_CONFIRM." in result

    def test_entities_shown_when_no_pending_action(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "last_intent": "weather",
            "last_entities": {"city": "NYC", "unit": "F"},
        })
        assert "Recent entities:" in result
        assert "city=NYC" in result

    def test_entities_suppressed_when_pending_action_present(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "last_intent": "calendar",
            "pending_action": {"type": "CALENDAR_CONFIRM", "data": {}},
            "last_entities": {"day": "today"},
        })
        assert "Recent entities" not in result

    def test_entities_capped_at_four(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({
            "last_intent": "weather",
            "last_entities": {
                "a": "1", "b": "2", "c": "3", "d": "4", "e": "5",
            },
        })
        assert result.count("=") == 4
        assert "e=5" not in result

    def test_private_class_hides_pending_data(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: True)
        result = rc._render_state_block({
            "last_intent": "send_message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "handler_class": "send_message",
                "data": {"display_name": "Secret", "body": "secret body"},
            },
        })
        assert "Secret" not in result
        assert "secret body" not in result
        assert "awaiting confirmation to send an SMS" in result

    def test_private_class_hides_entities(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: True)
        result = rc._render_state_block({
            "last_intent": "send_message",
            "last_entities": {"recipient": "Secret"},
        })
        assert "Recent entities" not in result
        assert "Secret" not in result

    def test_handler_class_used_for_privacy_check_when_present(self, monkeypatch):
        called_with = []
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: (called_with.append(cls), cls == "private_handler")[1])
        rc._render_state_block({
            "last_intent": "send_message",
            "pending_action": {
                "type": "X",
                "handler_class": "private_handler",
                "data": {"display_name": "Bob"},
            },
        })
        assert "private_handler" in called_with

    def test_handler_class_falls_back_to_intent(self, monkeypatch):
        called_with = []
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: (called_with.append(cls), False)[1])
        rc._render_state_block({
            "last_intent": "weather",
            "pending_action": {"type": "X", "data": {}},
        })
        assert "weather" in called_with

    def test_empty_packet_still_has_markers(self, monkeypatch):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        result = rc._render_state_block({})
        lines = result.splitlines()
        assert lines[0] == "[CURRENT CONVERSATION STATE]"
        assert lines[-1] == "[END CURRENT CONVERSATION STATE]"


# ─── _is_private_class ──────────────────────────────────────────────────


class TestPrivateClassLookup:
    def test_false_for_none_and_empty(self):
        assert rc._is_private_class(None) is False
        assert rc._is_private_class("") is False

    def test_import_failure_returns_false(self, monkeypatch):
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

    def test_privacy_for_raises_returns_false(self, monkeypatch):
        pkg = types.ModuleType("agent_skills")
        pkg.__path__ = []
        mod = types.ModuleType("agent_skills.private_handler_utils")
        mod.privacy_for = MagicMock(side_effect=RuntimeError("broken"))
        monkeypatch.setitem(sys.modules, "agent_skills", pkg)
        monkeypatch.setitem(sys.modules, "agent_skills.private_handler_utils", mod)

        assert rc._is_private_class("anything") is False


# ─── render_stage2_context ───────────────────────────────────────────────


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

    def test_default_max_turns_is_3(self, fake_recent_turns):
        fifo = fake_recent_turns(recent=["a"], state={})
        rc.render_stage2_context("session-1")
        fifo.get_recent.assert_called_once_with("session-1", n=3)

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
        assert "pending=SEND_MESSAGE_CONFIRMATION→Kathia" in result
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

    def test_no_pending_action_no_intent_returns_bare_prose(self, fake_recent_turns):
        fake_recent_turns(
            recent=["user: hi"],
            state={"pending_action": None, "last_intent": ""},
        )
        result = rc.render_stage2_context("session-1")
        assert result == "user: hi"


# ─── render_stage3_context ───────────────────────────────────────────────


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

    def test_default_max_turns_is_10(self, fake_recent_turns):
        fifo = fake_recent_turns(
            structured=[{"summary": "a", "privacy": "cloud_ok"}],
            state={},
        )
        rc.render_stage3_context("session-1")
        fifo.get_recent_structured.assert_called_once_with("session-1", n=10)

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

    def test_pending_action_without_last_intent_still_renders_state_block(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(
            structured=[{"summary": "turn", "privacy": "cloud_ok"}],
            state={
                "last_intent": "",
                "pending_action": {"type": "GENERIC", "data": {}},
            },
        )
        result = rc.render_stage3_context("session-1")
        assert "[CURRENT CONVERSATION STATE]" in result
        assert "- Pending action: GENERIC." in result

    def test_last_intent_without_pending_action_still_renders_state_block(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(
            structured=[{"summary": "turn", "privacy": "cloud_ok"}],
            state={
                "last_intent": "weather",
                "pending_action": None,
            },
        )
        result = rc.render_stage3_context("session-1")
        assert "[CURRENT CONVERSATION STATE]" in result
        assert "- Last intent: weather." in result

    def test_neither_pending_nor_intent_returns_bare_prose(
        self, fake_recent_turns
    ):
        fake_recent_turns(
            structured=[{"summary": "turn", "privacy": "cloud_ok"}],
            state={"last_intent": "", "pending_action": None},
        )
        result = rc.render_stage3_context("session-1")
        assert "[CURRENT CONVERSATION STATE]" not in result
        assert result == "turn"

    def test_stage3_always_passes_redact_local_only_true(
        self, fake_recent_turns
    ):
        fifo = fake_recent_turns(
            structured=[
                {"summary": "secret SMS", "privacy": "local_only", "intent": "send_message"},
            ],
            state={},
        )
        result = rc.render_stage3_context("session-1")
        fifo.get_recent_structured.assert_called_once()
        fifo.get_recent.assert_not_called()
        assert "secret SMS" not in result
        assert "private turn" in result


# ─── Integration points ─────────────────────────────────────────────────


class TestIntegrationPoints:
    def test_temp_sqlite_fifo_integration_reads_real_recent_turn_rows(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "vault_web" / "vault_web.db"

        try:
            from vault_web import database
        except ImportError:
            pytest.skip("vault_web not importable in this environment")

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


# ─── Structural invariants ──────────────────────────────────────────────


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

    def test_all_public_functions_never_raise_on_any_failure_path(
        self, monkeypatch
    ):
        _force_recent_turns_import_failure(monkeypatch)
        assert rc.get_recent_context("s") == ""
        assert rc.get_stage1_context_packet("s") == EMPTY_PACKET
        assert rc.render_stage2_context("s") == ""
        assert rc.render_stage3_context("s") == ""

    def test_stage3_marker_count_invariant_with_prose(
        self, fake_recent_turns, monkeypatch
    ):
        monkeypatch.setattr(rc, "_is_private_class", lambda cls: False)
        fake_recent_turns(
            structured=[{"summary": f"turn {i}", "privacy": "cloud_ok"} for i in range(5)],
            state={"last_intent": "test"},
        )
        result = rc.render_stage3_context("session-1")
        assert result.count("[CURRENT CONVERSATION STATE]") == 1
        assert result.count("[END CURRENT CONVERSATION STATE]") == 1

    def test_redaction_is_applied_on_stage3_cloud_bound_path(
        self, fake_recent_turns
    ):
        fake_recent_turns(
            structured=[
                {"summary": "PII data here", "privacy": "local_only", "intent": "send_message"},
                {"summary": "safe data", "privacy": "cloud_ok"},
            ],
            state={},
        )
        result = rc.render_stage3_context("session-1")
        assert "PII data here" not in result
        assert "safe data" in result
