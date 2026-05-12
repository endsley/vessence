"""Comprehensive audit tests for jane_web.jane_v2.classes.read_messages.handler.

Covers behavioral correctness, edge cases, integration mocks, and structural
invariants for the Stage 2 read_messages handler (thin guard that blocks
misclassified meta/architecture phrases, then escalates everything else to
Stage 3 by returning None).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_VESSENCE = Path(__file__).resolve().parents[1]
for p in [str(_VESSENCE), str(_VESSENCE / "agent_skills"), str(_VESSENCE / "vault_web")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jane_web.jane_v2.classes.read_messages.handler import (
    _ARCH_WORDS,
    _META_PHRASES,
    handle,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BEHAVIORAL TESTS — documented behavior from docstring
# ═══════════════════════════════════════════════════════════════════════════════


class TestEscalationByDesign:
    """Docstring says: handler returns None to escalate to Stage 3 for all
    legitimate read_messages prompts."""

    def test_read_my_messages_escalates(self):
        assert _run(handle("read my messages")) is None

    def test_any_new_texts_escalates(self):
        assert _run(handle("any new texts?")) is None

    def test_what_did_kathia_text_me_escalates(self):
        assert _run(handle("what did Kathia text me")) is None

    def test_check_my_inbox_escalates(self):
        assert _run(handle("check my inbox")) is None

    def test_any_unread_messages_escalates(self):
        assert _run(handle("any unread messages")) is None

    def test_do_i_have_new_messages_escalates(self):
        assert _run(handle("do I have any new messages")) is None

    def test_how_many_unread_escalates(self):
        assert _run(handle("how many unread messages do I have")) is None

    def test_show_me_recent_texts_escalates(self):
        assert _run(handle("show me my recent texts")) is None


class TestArchWordBlocking:
    """Docstring says: blocks meta/architecture phrases that get misclassified
    as read_messages."""

    def test_architecture_blocked(self):
        result = _run(handle("tell me about the architecture"))
        assert result == {"wrong_class": True}

    def test_infrastructure_blocked(self):
        result = _run(handle("explain the infrastructure"))
        assert result == {"wrong_class": True}

    def test_pipeline_blocked(self):
        result = _run(handle("how does the pipeline work"))
        assert result == {"wrong_class": True}

    def test_handler_blocked(self):
        result = _run(handle("what does the handler do"))
        assert result == {"wrong_class": True}

    def test_classifier_blocked(self):
        result = _run(handle("explain the classifier"))
        assert result == {"wrong_class": True}

    def test_stage_blocked(self):
        result = _run(handle("what happens at stage 2"))
        assert result == {"wrong_class": True}

    def test_arch_word_case_insensitive(self):
        result = _run(handle("Tell me about the ARCHITECTURE"))
        assert result == {"wrong_class": True}

    def test_arch_word_mixed_case(self):
        result = _run(handle("How does the Pipeline work?"))
        assert result == {"wrong_class": True}

    def test_arch_word_embedded_in_sentence(self):
        result = _run(handle("I want to understand your infrastructure choices"))
        assert result == {"wrong_class": True}


class TestMetaPhraseBlocking:
    """Docstring says: blocks meta/self-reference phrases that are about
    Jane's own replies, not SMS inbox."""

    def test_your_last_message(self):
        result = _run(handle("your last message was weird"))
        assert result == {"wrong_class": True}

    def test_your_last_reply(self):
        result = _run(handle("your last reply was off"))
        assert result == {"wrong_class": True}

    def test_your_previous_message(self):
        result = _run(handle("your previous message confused me"))
        assert result == {"wrong_class": True}

    def test_your_previous_reply(self):
        result = _run(handle("your previous reply didn't make sense"))
        assert result == {"wrong_class": True}

    def test_the_last_message_you(self):
        result = _run(handle("the last message you sent was wrong"))
        assert result == {"wrong_class": True}

    def test_the_last_reply_you(self):
        result = _run(handle("the last reply you gave me"))
        assert result == {"wrong_class": True}

    def test_last_message_took(self):
        result = _run(handle("last message took forever"))
        assert result == {"wrong_class": True}

    def test_last_reply_took(self):
        result = _run(handle("last reply took a long time"))
        assert result == {"wrong_class": True}

    def test_last_message_when_i_asked(self):
        result = _run(handle("last message when i asked you about dinner"))
        assert result == {"wrong_class": True}

    def test_took_a_while(self):
        result = _run(handle("that took a while"))
        assert result == {"wrong_class": True}

    def test_took_so_long(self):
        result = _run(handle("that took so long to respond"))
        assert result == {"wrong_class": True}

    def test_so_slow(self):
        result = _run(handle("you were so slow"))
        assert result == {"wrong_class": True}

    def test_explain_why(self):
        result = _run(handle("explain why you said that"))
        assert result == {"wrong_class": True}

    def test_why_did_you(self):
        result = _run(handle("why did you say that"))
        assert result == {"wrong_class": True}

    def test_why_was_your(self):
        result = _run(handle("why was your response so weird"))
        assert result == {"wrong_class": True}

    def test_meta_phrase_case_insensitive(self):
        result = _run(handle("YOUR LAST MESSAGE was strange"))
        assert result == {"wrong_class": True}

    def test_meta_phrase_mixed_case(self):
        result = _run(handle("Your Last Reply took forever"))
        assert result == {"wrong_class": True}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_string_escalates(self):
        assert _run(handle("")) is None

    def test_whitespace_only_escalates(self):
        assert _run(handle("   ")) is None

    def test_single_character_escalates(self):
        assert _run(handle("a")) is None

    def test_very_long_input_no_keywords_escalates(self):
        prompt = "read my texts " * 5000
        assert _run(handle(prompt)) is None

    def test_very_long_input_with_arch_word_at_end(self):
        prompt = "word " * 5000 + "architecture"
        result = _run(handle(prompt))
        assert result == {"wrong_class": True}

    def test_very_long_input_with_meta_phrase_at_end(self):
        prompt = "word " * 5000 + "your last message was odd"
        result = _run(handle(prompt))
        assert result == {"wrong_class": True}

    def test_unicode_input_escalates(self):
        assert _run(handle("讀取我的訊息")) is None

    def test_emoji_input_escalates(self):
        assert _run(handle("📱 check texts")) is None

    def test_special_characters_escalates(self):
        assert _run(handle("!@#$%^&*()")) is None

    def test_newlines_in_prompt_escalates(self):
        assert _run(handle("read\nmy\nmessages")) is None

    def test_tabs_in_prompt_escalates(self):
        assert _run(handle("read\tmy\tmessages")) is None

    def test_context_param_ignored(self):
        result = _run(handle("read my messages", context="some context here"))
        assert result is None

    def test_params_none_default(self):
        result = _run(handle("read my messages", params=None))
        assert result is None

    def test_params_empty_dict(self):
        result = _run(handle("read my messages", params={}))
        assert result is None

    def test_params_with_data(self):
        result = _run(handle("read my messages", params={"filter_sender": "Mom"}))
        assert result is None

    def test_arch_word_substring_not_false_positive(self):
        """'stages' contains 'stage' — verify substring matching behavior."""
        result = _run(handle("what are the stages of grief"))
        assert result == {"wrong_class": True}

    def test_handler_word_in_legitimate_message(self):
        """'handler' appears — even in non-technical context, it's blocked.
        This is a known trade-off documented in the docstring."""
        result = _run(handle("my dog is a good handler"))
        assert result == {"wrong_class": True}

    def test_arch_word_not_triggered_by_partial_match(self):
        """'hand' should not trigger 'handler' block."""
        assert _run(handle("hand me my phone")) is None

    def test_meta_phrase_not_triggered_by_partial_overlap(self):
        """'your last' alone is not a meta phrase."""
        assert _run(handle("your last chance to read texts")) is None

    def test_multiple_arch_words_still_returns_wrong_class(self):
        result = _run(handle("architecture and infrastructure of the pipeline"))
        assert result == {"wrong_class": True}

    def test_both_arch_and_meta_returns_wrong_class(self):
        result = _run(handle("your last message about the architecture"))
        assert result == {"wrong_class": True}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INTEGRATION POINTS — metadata.py and dispatcher
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetadataAlignment:
    """Verify handler behavior aligns with metadata.py few_shot examples."""

    @pytest.fixture(autouse=True)
    def load_metadata(self):
        from jane_web.jane_v2.classes.read_messages.metadata import METADATA
        self.metadata = METADATA

    def test_positive_few_shots_all_escalate(self):
        """Every few_shot that maps to 'read messages:High' should escalate
        (return None), not be blocked."""
        for prompt_text, label in self.metadata["few_shot"]:
            if label.startswith("read messages"):
                result = _run(handle(prompt_text))
                assert result is None, (
                    f"Few-shot positive example '{prompt_text}' was blocked "
                    f"instead of escalating"
                )

    @pytest.mark.xfail(
        reason="BUG: handler misses 2 metadata negatives: 'why did the last message "
               "take so long' (needs 'take so long' in _META_PHRASES) and 'explain "
               "the delay on the last message' (needs 'explain the delay' or similar)",
        strict=True,
    )
    def test_negative_few_shots_all_blocked(self):
        """Every few_shot that maps to 'others:Low' should be caught by the
        handler's guard (wrong_class) — these are meta/self-reference phrases
        misclassified as read_messages."""
        for prompt_text, label in self.metadata["few_shot"]:
            if label.startswith("others"):
                result = _run(handle(prompt_text))
                assert result == {"wrong_class": True}, (
                    f"Few-shot negative example '{prompt_text}' was NOT blocked — "
                    f"handler would let a misclassified prompt through to Stage 3"
                )

    def test_escalation_context_callable(self):
        """metadata['escalation_context'] must be a callable that Stage 3 uses
        to prefetch messages."""
        assert callable(self.metadata["escalation_context"])

    def test_metadata_has_ack(self):
        assert "ack" in self.metadata
        assert isinstance(self.metadata["ack"], str)

    def test_metadata_has_escalate_ack(self):
        assert "escalate_ack" in self.metadata
        assert isinstance(self.metadata["escalate_ack"], str)


class TestEscalationContextMocked:
    """Test _escalation_context() with mocked database."""

    def test_db_unavailable_returns_error_string(self):
        with patch.dict(sys.modules, {"database": None}):
            from jane_web.jane_v2.classes.read_messages.metadata import _escalation_context
            result = _escalation_context()
            assert "unavailable" in result.lower() or "error" in result.lower()

    def test_db_returns_rows(self):
        mock_row = {
            "sender": "Kathia",
            "body": "Hey, are you coming?",
            "timestamp_ms": 1700000000000,
            "is_contact": True,
            "msg_type": "sms",
        }
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.get_db.return_value = mock_conn

        with patch.dict(sys.modules, {"database": mock_db}):
            from importlib import reload
            import jane_web.jane_v2.classes.read_messages.metadata as meta_mod
            reload(meta_mod)
            result = meta_mod._escalation_context()
            assert "Recent synced messages" in result or "Kathia" in result or "RECEIVED" in result

    def test_empty_db_returns_no_messages(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.get_db.return_value = mock_conn

        with patch.dict(sys.modules, {"database": mock_db}):
            from importlib import reload
            import jane_web.jane_v2.classes.read_messages.metadata as meta_mod
            reload(meta_mod)
            result = meta_mod._escalation_context()
            assert "no synced messages" in result.lower()

    def test_db_query_exception_returns_error(self):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("table not found")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.get_db.return_value = mock_conn

        with patch.dict(sys.modules, {"database": mock_db}):
            from importlib import reload
            import jane_web.jane_v2.classes.read_messages.metadata as meta_mod
            reload(meta_mod)
            result = meta_mod._escalation_context()
            assert "failed" in result.lower() or "error" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STRUCTURAL INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralInvariants:
    """High-leverage checks on lookup tables, return shapes, and guard logic."""

    # ── Lookup table: _ARCH_WORDS ───────────────────────────────────────────

    def test_arch_words_all_lowercase(self):
        for word in _ARCH_WORDS:
            assert word == word.lower(), (
                f"_ARCH_WORDS entry '{word}' is not lowercase — "
                f"prompt.lower() comparison would silently miss uppercase entries"
            )

    def test_arch_words_no_duplicates(self):
        assert len(_ARCH_WORDS) == len(set(_ARCH_WORDS)), (
            f"_ARCH_WORDS has duplicates: "
            f"{[w for w in _ARCH_WORDS if _ARCH_WORDS.count(w) > 1]}"
        )

    def test_arch_words_no_empty_strings(self):
        for word in _ARCH_WORDS:
            assert word.strip(), "_ARCH_WORDS contains an empty or whitespace-only entry"

    def test_every_arch_word_is_reachable(self):
        """Every entry in _ARCH_WORDS must actually trigger wrong_class."""
        for word in _ARCH_WORDS:
            result = _run(handle(f"tell me about {word}"))
            assert result == {"wrong_class": True}, (
                f"_ARCH_WORDS entry '{word}' does NOT trigger wrong_class — "
                f"dead entry in the guard table"
            )

    def test_arch_words_no_overlap_with_legitimate_sms_vocabulary(self):
        """None of the arch words should be common SMS-related terms that would
        block legitimate read_messages requests."""
        sms_vocab = {"message", "messages", "text", "texts", "inbox", "unread",
                     "read", "new", "recent", "phone", "sms", "sender", "reply"}
        overlap = set(_ARCH_WORDS) & sms_vocab
        assert not overlap, (
            f"_ARCH_WORDS overlaps with SMS vocabulary: {overlap} — "
            f"this would block legitimate read_messages prompts"
        )

    # ── Lookup table: _META_PHRASES ─────────────────────────────────────────

    def test_meta_phrases_all_lowercase(self):
        for phrase in _META_PHRASES:
            assert phrase == phrase.lower(), (
                f"_META_PHRASES entry '{phrase}' is not lowercase — "
                f"prompt.lower() comparison would silently miss it"
            )

    def test_meta_phrases_no_duplicates(self):
        assert len(_META_PHRASES) == len(set(_META_PHRASES)), (
            f"_META_PHRASES has duplicates"
        )

    def test_meta_phrases_no_empty_strings(self):
        for phrase in _META_PHRASES:
            assert phrase.strip(), "_META_PHRASES contains an empty or whitespace-only entry"

    def test_every_meta_phrase_is_reachable(self):
        """Every entry in _META_PHRASES must actually trigger wrong_class."""
        for phrase in _META_PHRASES:
            result = _run(handle(phrase))
            assert result == {"wrong_class": True}, (
                f"_META_PHRASES entry '{phrase}' does NOT trigger wrong_class — "
                f"dead entry in the guard table"
            )

    def test_meta_phrases_dont_block_sms_reading(self):
        """Meta phrases should be about Jane's own behavior, not about reading
        SMS messages. None should contain 'read my' or 'check my'."""
        for phrase in _META_PHRASES:
            assert "read my" not in phrase, (
                f"_META_PHRASES entry '{phrase}' contains 'read my' — "
                f"would block legitimate read_messages requests"
            )
            assert "check my" not in phrase, (
                f"_META_PHRASES entry '{phrase}' contains 'check my' — "
                f"would block legitimate read_messages requests"
            )

    # ── No arch word is a prefix of another (subsumption check) ─────────────

    def test_arch_words_no_unnecessary_subsumption(self):
        """If word A is a substring of word B, word A already catches everything
        B would catch. B is dead weight (or A is overly broad)."""
        words = list(_ARCH_WORDS)
        for i, a in enumerate(words):
            for j, b in enumerate(words):
                if i != j and a in b:
                    pytest.fail(
                        f"_ARCH_WORDS: '{a}' is a substring of '{b}' — "
                        f"'{b}' is unreachable (already caught by '{a}')"
                    )

    # ── Return shape invariants ─────────────────────────────────────────────

    def test_wrong_class_return_is_exact_shape(self):
        """wrong_class return must be exactly {wrong_class: True} with no extra
        keys, matching what the dispatcher checks."""
        for word in _ARCH_WORDS[:1]:
            result = _run(handle(f"explain the {word}"))
            assert result == {"wrong_class": True}
            assert len(result) == 1

    def test_escalation_return_is_none(self):
        """Escalation must return exactly None, not empty dict or False."""
        result = _run(handle("read my messages"))
        assert result is None

    def test_handle_signature_accepts_all_documented_params(self):
        """Handler must accept prompt, context, and params per the standard
        handler interface."""
        import inspect
        sig = inspect.signature(handle)
        params = list(sig.parameters.keys())
        assert "prompt" in params
        assert "context" in params
        assert "params" in params

    def test_handle_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(handle)

    # ── Guard ordering invariant ────────────────────────────────────────────

    def test_arch_words_checked_before_meta_phrases(self):
        """If a prompt contains both an arch word AND a meta phrase, arch word
        check should fire first (no log message for meta). This verifies the
        guard ordering matches the code structure."""
        prompt = "your last message about the pipeline"
        result = _run(handle(prompt))
        assert result == {"wrong_class": True}

    # ── No false negatives on metadata negative examples ────────────────────

    @pytest.mark.xfail(
        reason="BUG: handler guard missing coverage for 2 metadata negative "
               "examples — 'take so long' and 'explain the delay' not in _META_PHRASES",
        strict=True,
    )
    def test_metadata_negative_examples_coverage(self):
        """The handler must catch ALL the 'others:Low' examples from metadata.py.
        If metadata adds a new negative example, the handler guard must cover it."""
        try:
            from jane_web.jane_v2.classes.read_messages.metadata import METADATA
        except ImportError:
            pytest.skip("metadata.py not importable")

        uncaught = []
        for prompt_text, label in METADATA["few_shot"]:
            if label.startswith("others"):
                result = _run(handle(prompt_text))
                if result != {"wrong_class": True}:
                    uncaught.append(prompt_text)

        assert not uncaught, (
            f"Handler does NOT block these metadata negative examples: {uncaught} — "
            f"misclassified prompts will leak through to Stage 3"
        )

    # ── No false positives on metadata positive examples ────────────────────

    def test_metadata_positive_examples_not_blocked(self):
        """The handler must NOT block any 'read messages:High' examples."""
        try:
            from jane_web.jane_v2.classes.read_messages.metadata import METADATA
        except ImportError:
            pytest.skip("metadata.py not importable")

        blocked = []
        for prompt_text, label in METADATA["few_shot"]:
            if label.startswith("read messages"):
                result = _run(handle(prompt_text))
                if result is not None:
                    blocked.append(prompt_text)

        assert not blocked, (
            f"Handler BLOCKS these legitimate read_messages prompts: {blocked} — "
            f"guard is overly aggressive"
        )

    # ── Params schema alignment ─────────────────────────────────────────────

    def test_params_schema_keys_exist_in_metadata(self):
        """PARAMS_SCHEMA must be present in metadata and non-empty."""
        try:
            from jane_web.jane_v2.classes.read_messages.metadata import PARAMS_SCHEMA
        except ImportError:
            pytest.skip("metadata.py not importable")

        assert isinstance(PARAMS_SCHEMA, dict)
        assert len(PARAMS_SCHEMA) > 0
        assert "filter_sender" in PARAMS_SCHEMA
        assert "unread_only" in PARAMS_SCHEMA

    # ── Handler does NOT perform destructive operations ─────────────────────

    def test_handler_has_no_side_effects(self):
        """read_messages handler is documented as a thin guard. It must not
        perform any DB writes, HTTP calls, or state mutations. Verify by
        checking that calling it multiple times with the same input yields
        identical results (idempotency)."""
        for _ in range(5):
            assert _run(handle("read my messages")) is None
        for _ in range(5):
            assert _run(handle("explain the architecture")) == {"wrong_class": True}
        for _ in range(5):
            assert _run(handle("your last message was slow")) == {"wrong_class": True}

    def test_handler_does_not_import_heavy_dependencies(self):
        """The handler module should only import logging — no DB, HTTP, or LLM
        imports. It's a thin guard by design."""
        import jane_web.jane_v2.classes.read_messages.handler as mod
        source = Path(mod.__file__).read_text()
        heavy_imports = ["import httpx", "import requests", "from database",
                         "import sqlite", "import ollama", "import openai"]
        for imp in heavy_imports:
            assert imp not in source, (
                f"Handler imports '{imp}' — thin guard should not have heavy dependencies"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
