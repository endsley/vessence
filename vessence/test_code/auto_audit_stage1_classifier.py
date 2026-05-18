"""Auto-audit tests for jane_web.jane_v2.stage1_classifier.

Covers behavioral tests, edge cases, integration mocks, and structural
invariants including Contract 5 (stage routing decisions).
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

from jane_web.jane_v2.stage1_classifier import (
    FORCE_STAGE3_PHRASES,
    PROVEN_CLASSES,
    STRICT_CLASSES,
    _CLASS_MAP,
    _END_CONVERSATION_RE,
    _FORCE_STAGE3_RE,
    _GATE_NEW,
    _GATE_PROVEN,
    _GATE_STRICT,
    _STRICT_KEYWORDS,
    _clinic_schedule_ok,
    _end_conversation_phrase_ok,
    _gate_for,
    _strict_keyword_ok,
    _strip_system_markers,
    classify,
)

CLASSES_DIR = VESSENCE_ROOT / "jane_web" / "jane_v2" / "classes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mock_classify_result(cls="WEATHER", confidence=0.90, margin=0.50, min_dist=0.10):
    return {
        "classification": cls,
        "confidence": confidence,
        "margin": margin,
        "min_dist": min_dist,
        "latency_ms": 5.0,
    }


@pytest.fixture
def mock_stage1():
    mock_fn = AsyncMock()
    fake_module = type(sys)("intent_classifier.v2.classifier")
    fake_module.stage1_classify = mock_fn
    with patch.dict(sys.modules, {
        "intent_classifier": type(sys)("intent_classifier"),
        "intent_classifier.v2": type(sys)("intent_classifier.v2"),
        "intent_classifier.v2.classifier": fake_module,
    }):
        yield mock_fn


# ---------------------------------------------------------------------------
# 1. STRUCTURAL INVARIANTS — _CLASS_MAP
# ---------------------------------------------------------------------------

class TestClassMapStructure:
    """Every _CLASS_MAP value must correspond to a real class pack directory."""

    def test_all_class_map_values_have_directories(self):
        registry_names = set(_CLASS_MAP.values())
        existing_dirs = {
            d.name
            for d in CLASSES_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(("_", "."))
        }
        for pipeline_name in registry_names:
            dir_name = pipeline_name.replace(" ", "_")
            assert dir_name in existing_dirs, (
                f"_CLASS_MAP value {pipeline_name!r} (dir={dir_name!r}) "
                f"has no class pack directory in {CLASSES_DIR}"
            )

    def test_delegate_opus_maps_to_others(self):
        assert _CLASS_MAP["DELEGATE_OPUS"] == "others"

    def test_force_stage3_maps_to_others(self):
        assert _CLASS_MAP["FORCE_STAGE3"] == "others"

    def test_no_class_map_key_is_empty(self):
        for k, v in _CLASS_MAP.items():
            assert k, "Empty key in _CLASS_MAP"
            assert v, f"Empty value for _CLASS_MAP[{k!r}]"

    def test_proven_classes_are_in_class_map(self):
        for cls in PROVEN_CLASSES:
            assert cls in _CLASS_MAP, (
                f"PROVEN_CLASSES member {cls!r} is not a key in _CLASS_MAP"
            )

    def test_strict_classes_are_in_class_map(self):
        for cls in STRICT_CLASSES:
            assert cls in _CLASS_MAP, (
                f"STRICT_CLASSES member {cls!r} is not a key in _CLASS_MAP"
            )

    def test_strict_classes_all_have_keyword_guards(self):
        for cls in STRICT_CLASSES:
            assert cls in _STRICT_KEYWORDS, (
                f"STRICT_CLASSES member {cls!r} has no entry in _STRICT_KEYWORDS — "
                f"unanimous embedding votes could fire without a keyword check"
            )

    def test_strict_keywords_only_cover_strict_classes(self):
        for cls in _STRICT_KEYWORDS:
            assert cls in STRICT_CLASSES, (
                f"_STRICT_KEYWORDS has entry for {cls!r} but it's not in STRICT_CLASSES"
            )

    def test_no_overlap_proven_and_strict(self):
        overlap = PROVEN_CLASSES & STRICT_CLASSES
        assert not overlap, (
            f"Classes in both PROVEN and STRICT sets: {overlap}. "
            f"STRICT uses _GATE_STRICT which overrides PROVEN thresholds."
        )


# ---------------------------------------------------------------------------
# 2. CONTRACT 5 — "others" must always be Low
# ---------------------------------------------------------------------------

class TestOthersAlwaysLow:
    """Contract 5: the 'others' fallback class must never return High confidence."""

    def test_delegate_opus_returns_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "DELEGATE_OPUS", confidence=1.0, margin=1.0
        )
        cls, conf, _ = _run(classify("hello"))
        assert cls == "others"
        assert conf == "Low"

    def test_unknown_class_returns_others_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "NONEXISTENT_CLASS", confidence=1.0, margin=1.0
        )
        cls, conf, _ = _run(classify("hello"))
        assert cls == "others"
        assert conf == "Low"

    def test_force_stage3_returns_others_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "FORCE_STAGE3", confidence=1.0, margin=1.0
        )
        cls, conf, _ = _run(classify("hello"))
        assert cls == "others"
        assert conf == "Low"


# ---------------------------------------------------------------------------
# 3. CONTRACT 5 — destructive classes need strict confidence
# ---------------------------------------------------------------------------

class TestEndConversationStrictness:
    """END_CONVERSATION must require ≥ 0.80 confidence floor and a phrase match."""

    def test_end_conversation_below_080_is_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "END_CONVERSATION", confidence=0.79, margin=0.50
        )
        cls, conf, _ = _run(classify("bye"))
        assert conf == "Low", "END_CONVERSATION below 0.80 must be demoted to Low"

    def test_end_conversation_at_080_and_phrase_match_is_high(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "END_CONVERSATION", confidence=0.80, margin=0.50
        )
        cls, conf, _ = _run(classify("goodbye"))
        assert conf == "High"
        assert cls == "end conversation"

    def test_end_conversation_high_conf_but_no_phrase_is_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "END_CONVERSATION", confidence=1.0, margin=1.0
        )
        cls, conf, _ = _run(classify(
            "I think setting the context window to 1024 is not long enough"
        ))
        assert conf == "Low", (
            "END_CONVERSATION should not fire on sentences that merely contain "
            "end-conversation keywords"
        )

    def test_end_conversation_ambiguous_technical_sentence(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "END_CONVERSATION", confidence=0.95, margin=0.60
        )
        cls, conf, _ = _run(classify("Can you stop the timer and cancel the job?"))
        assert conf == "Low"


# ---------------------------------------------------------------------------
# 4. BEHAVIORAL — _strip_system_markers
# ---------------------------------------------------------------------------

class TestStripSystemMarkers:
    def test_strips_tool_result_prefix(self):
        raw = '[TOOL_RESULT:{"tool":"clock","status":"ok"}] what time is it'
        cleaned = _strip_system_markers(raw)
        assert "TOOL_RESULT" not in cleaned
        assert "what time is it" in cleaned

    def test_strips_nested_tool_result(self):
        raw = '[TOOL_RESULT:{"tool":"sms","data":{"id":1,"body":"hi"}}] any messages?'
        cleaned = _strip_system_markers(raw)
        assert "TOOL_RESULT" not in cleaned
        assert "any messages" in cleaned

    def test_strips_sms_send_request_marker(self):
        raw = (
            "[SMS SEND REQUEST to +1234567890]\n"
            "body here\n"
            "[END SMS SEND REQUEST]\n"
            "did it send?"
        )
        cleaned = _strip_system_markers(raw)
        assert "SMS SEND REQUEST" not in cleaned
        assert "did it send?" in cleaned

    def test_strips_phone_tool_results_marker(self):
        raw = (
            "[PHONE TOOL RESULTS]\n"
            "some results here\n"
            "[END PHONE TOOL RESULTS]\n"
            "what happened?"
        )
        cleaned = _strip_system_markers(raw)
        assert "PHONE TOOL RESULTS" not in cleaned
        assert "what happened?" in cleaned

    def test_strips_truncated_sms_send_request(self):
        raw = "hello [SMS SEND REQUEST to +1234567890]\ntruncated body"
        cleaned = _strip_system_markers(raw)
        assert "SMS SEND REQUEST" not in cleaned
        assert "hello" in cleaned

    def test_strips_subject_change_prefix(self):
        assert _strip_system_markers("change the subject to weather") == "weather"
        assert _strip_system_markers("let's talk about music") == "music"
        assert _strip_system_markers("switch the topic to cooking") == "cooking"
        assert _strip_system_markers("I'd like to change the subject to news") == "news"

    def test_strips_subject_change_variations(self):
        assert _strip_system_markers("can we switch the conversation to sports") == "sports"
        assert _strip_system_markers("lets discuss the budget") == "the budget"
        assert _strip_system_markers("I want to change the topic to AI") == "AI"
        assert _strip_system_markers("please shift the subject to gardening") == "gardening"

    def test_plural_fixup_weathers(self):
        assert "weather" in _strip_system_markers("how are the weathers today")
        assert "weathers" not in _strip_system_markers("how are the weathers today")

    def test_returns_original_if_fully_stripped(self):
        marker_only = '[TOOL_RESULT:{"status":"ok"}]'
        result = _strip_system_markers(marker_only)
        assert result == marker_only

    def test_preserves_plain_text(self):
        plain = "What's the weather like in Tokyo?"
        assert _strip_system_markers(plain) == plain


# ---------------------------------------------------------------------------
# 5. BEHAVIORAL — _gate_for
# ---------------------------------------------------------------------------

class TestGateFor:
    def test_strict_class_gets_strict_gate(self):
        for cls in STRICT_CLASSES:
            assert _gate_for(cls) == _GATE_STRICT

    def test_proven_class_gets_proven_gate(self):
        for cls in PROVEN_CLASSES:
            if cls not in STRICT_CLASSES:
                assert _gate_for(cls) == _GATE_PROVEN

    def test_unknown_class_gets_new_gate(self):
        assert _gate_for("SOME_NEW_CLASS") == _GATE_NEW

    def test_gate_thresholds_ordering(self):
        assert _GATE_NEW["conf"] > _GATE_PROVEN["conf"], (
            "New classes should require higher confidence than proven ones"
        )
        assert _GATE_STRICT["conf"] >= _GATE_NEW["conf"], (
            "Strict classes should require at least as much confidence as new ones"
        )


# ---------------------------------------------------------------------------
# 6. BEHAVIORAL — _strict_keyword_ok
# ---------------------------------------------------------------------------

class TestStrictKeywordOk:
    def test_non_strict_class_always_passes(self):
        assert _strict_keyword_ok("WEATHER", "any old text")
        assert _strict_keyword_ok("GREETING", "hello there")

    def test_read_messages_requires_keyword(self):
        assert _strict_keyword_ok("READ_MESSAGES", "read my text messages")
        assert _strict_keyword_ok("READ_MESSAGES", "any new sms?")
        assert not _strict_keyword_ok("READ_MESSAGES", "any updates from yesterday")

    def test_read_email_requires_keyword(self):
        assert _strict_keyword_ok("READ_EMAIL", "check my email")
        assert _strict_keyword_ok("READ_EMAIL", "what's in my gmail?")
        assert not _strict_keyword_ok("READ_EMAIL", "any updates from yesterday")

    def test_read_calendar_requires_keyword(self):
        assert _strict_keyword_ok("READ_CALENDAR", "what's on my calendar")
        assert _strict_keyword_ok("READ_CALENDAR", "show my schedule")
        assert not _strict_keyword_ok("READ_CALENDAR", "what's happening today")

    def test_sync_messages_requires_keyword(self):
        assert _strict_keyword_ok("SYNC_MESSAGES", "sync my text messages")
        assert not _strict_keyword_ok("SYNC_MESSAGES", "update everything")

    def test_keyword_blocks_reschedule(self):
        assert not _strict_keyword_ok("READ_CALENDAR", "reschedule the meeting")

    def test_keyword_allows_plurals(self):
        assert _strict_keyword_ok("READ_EMAIL", "check my emails")
        assert _strict_keyword_ok("READ_MESSAGES", "read messages")

    def test_keyword_case_insensitive(self):
        assert _strict_keyword_ok("READ_EMAIL", "Check my EMAIL")
        assert _strict_keyword_ok("READ_MESSAGES", "Read SMS")


# ---------------------------------------------------------------------------
# 7. BEHAVIORAL — _clinic_schedule_ok
# ---------------------------------------------------------------------------

class TestClinicScheduleOk:
    def test_no_my_schedule_passes(self):
        assert _clinic_schedule_ok("show clinic hours")
        assert _clinic_schedule_ok("when are patients coming")

    def test_my_schedule_without_clinic_keyword_fails(self):
        assert not _clinic_schedule_ok("what's on my schedule today")
        assert not _clinic_schedule_ok("show my schedule")

    def test_my_schedule_with_clinic_keyword_passes(self):
        assert _clinic_schedule_ok("what's on my schedule at the clinic")
        assert _clinic_schedule_ok("my schedule for patients today")
        assert _clinic_schedule_ok("my schedule with kathia")


# ---------------------------------------------------------------------------
# 8. BEHAVIORAL — _end_conversation_phrase_ok
# ---------------------------------------------------------------------------

class TestEndConversationPhraseOk:
    @pytest.mark.parametrize("phrase", [
        "bye", "goodbye", "bye jane", "good night", "goodnight jane",
        "see you later", "talk later", "thanks", "thank you",
        "I'm done", "we're done", "all done", "that's all",
        "end conversation", "conversation over", "close conversation",
        "stop", "stop listening", "stop talking",
        "cancel", "dismiss", "be quiet", "shut up", "silence",
        "nevermind", "forget it", "drop it", "abort",
        "no thanks", "nope", "nah", "not now", "skip it",
        "go away", "leave me alone",
        "I'm good", "all good", "we're good", "all set",
        "ok cool", "ok great", "ok thanks", "ok done",
        "over and out",
    ])
    def test_valid_end_phrases(self, phrase):
        assert _end_conversation_phrase_ok(phrase), f"Should accept: {phrase!r}"

    @pytest.mark.parametrize("phrase", [
        "I think setting the context window to 1024 is not long enough",
        "Can you stop the timer and cancel the job?",
        "Tell me about the end of the conversation in the movie",
        "What does silence mean in buddhism?",
        "I need to cancel my subscription how do I do that",
        "The drop in temperature is concerning",
        "Thank you for explaining, but I have another question",
        "Stop and think about this for a second",
        "Enough about weather, what about news?",
    ])
    def test_rejects_embedded_keywords(self, phrase):
        assert not _end_conversation_phrase_ok(phrase), f"Should reject: {phrase!r}"

    def test_handles_none(self):
        assert not _end_conversation_phrase_ok(None)

    def test_handles_empty(self):
        assert not _end_conversation_phrase_ok("")

    def test_handles_smart_quotes(self):
        assert _end_conversation_phrase_ok("that’s all")
        assert _end_conversation_phrase_ok("I’m done")

    def test_handles_trailing_punctuation(self):
        assert _end_conversation_phrase_ok("bye!")
        assert _end_conversation_phrase_ok("goodbye.")
        assert _end_conversation_phrase_ok("thanks?")

    def test_handles_extra_whitespace(self):
        assert _end_conversation_phrase_ok("  bye  ")
        assert _end_conversation_phrase_ok("goodbye\n")


# ---------------------------------------------------------------------------
# 9. BEHAVIORAL — FORCE_STAGE3 override
# ---------------------------------------------------------------------------

class TestForceStage3:
    @pytest.mark.parametrize("phrase", [
        "think deeply about this problem",
        "use stage 3 for this",
        "escalate to the main brain",
        "think carefully about the architecture",
        "stage three please",
        "reason deeply about this",
    ])
    def test_force_stage3_phrases_bypass_chromadb(self, phrase, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 1.0, 1.0)
        cls, conf, dist = _run(classify(phrase))
        assert cls == "others"
        assert conf == "Low"
        assert dist == 1.0
        mock_stage1.assert_not_called()

    def test_force_stage3_regex_fallback(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 1.0, 1.0)
        cls, conf, _ = _run(classify("think this through"))
        assert cls == "others"
        assert conf == "Low"
        mock_stage1.assert_not_called()

    def test_force_stage3_regex_with_intervening_words(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 1.0, 1.0)
        cls, conf, _ = _run(classify("think about it carefully"))
        assert cls == "others"
        assert conf == "Low"

    def test_normal_think_does_not_trigger(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.90, 0.50)
        cls, conf, _ = _run(classify("I think it will rain"))
        assert cls == "weather"
        assert conf == "High"


# ---------------------------------------------------------------------------
# 10. INTEGRATION — classify() with mocked ChromaDB
# ---------------------------------------------------------------------------

class TestClassifyIntegration:
    def test_returns_3_tuple(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.90, 0.50)
        result = _run(classify("what's the weather"))
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_high_confidence_proven_class(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.90, 0.50)
        cls, conf, dist = _run(classify("what's the weather"))
        assert cls == "weather"
        assert conf == "High"
        assert isinstance(dist, float)

    def test_low_confidence_below_gate(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.50, 0.10)
        cls, conf, _ = _run(classify("what's the weather"))
        assert cls == "weather"
        assert conf == "Low"

    def test_new_class_needs_higher_threshold(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "SOME_NEW_CLASS_NOT_IN_MAP", confidence=0.70, margin=0.30
        )
        cls, conf, _ = _run(classify("something new"))
        assert cls == "others"
        assert conf == "Low"

    def test_chromadb_failure_returns_others_low(self, mock_stage1):
        mock_stage1.side_effect = Exception("ChromaDB connection error")
        cls, conf, dist = _run(classify("hello"))
        assert cls == "others"
        assert conf == "Low"
        assert dist == 1.0

    def test_strict_class_unanimous_with_keyword(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "READ_MESSAGES", confidence=1.0, margin=0.50
        )
        cls, conf, _ = _run(classify("read my text messages"))
        assert cls == "read messages"
        assert conf == "High"

    def test_strict_class_unanimous_without_keyword(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "READ_MESSAGES", confidence=1.0, margin=0.50
        )
        cls, conf, _ = _run(classify("any updates from yesterday"))
        assert cls == "read messages"
        assert conf == "Low"

    def test_strict_class_below_unanimous(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "READ_MESSAGES", confidence=0.80, margin=0.30
        )
        cls, conf, _ = _run(classify("read my text messages"))
        assert cls == "read messages"
        assert conf == "Low"

    def test_clinic_schedule_personal_rejected(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "CLINIC_SCHEDULES_INFO", confidence=0.90, margin=0.50
        )
        cls, conf, _ = _run(classify("what's on my schedule today"))
        assert cls == "clinic schedules info"
        assert conf == "Low"

    def test_clinic_schedule_with_clinic_keyword(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "CLINIC_SCHEDULES_INFO", confidence=0.90, margin=0.50
        )
        cls, conf, _ = _run(classify("what's on my schedule at the clinic"))
        assert cls == "clinic schedules info"
        assert conf == "High"

    def test_min_dist_passthrough(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "GREETING", confidence=0.90, margin=0.50, min_dist=0.05
        )
        _, _, dist = _run(classify("hello"))
        assert dist == pytest.approx(0.05)

    def test_missing_min_dist_defaults_to_1(self, mock_stage1):
        mock_stage1.return_value = {
            "classification": "GREETING",
            "confidence": 0.90,
            "margin": 0.50,
        }
        _, _, dist = _run(classify("hello"))
        assert dist == 1.0

    def test_session_id_accepted(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("GREETING", 0.90, 0.50)
        cls, conf, _ = _run(classify("hello", session_id="test-session"))
        assert cls == "greeting"

    def test_system_markers_stripped_before_classification(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.90, 0.50)
        raw = '[TOOL_RESULT:{"status":"ok"}] what is the weather'
        _run(classify(raw))
        call_arg = mock_stage1.call_args[0][0]
        assert "TOOL_RESULT" not in call_arg
        assert "weather" in call_arg.lower()


# ---------------------------------------------------------------------------
# 11. EDGE CASES
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("DELEGATE_OPUS", 0.50, 0.10)
        cls, conf, _ = _run(classify(""))
        assert cls == "others"
        assert conf == "Low"

    def test_whitespace_only(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("DELEGATE_OPUS", 0.50, 0.10)
        cls, conf, _ = _run(classify("   \n\t  "))
        assert cls == "others"
        assert conf == "Low"

    def test_very_long_input(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("WEATHER", 0.90, 0.50)
        long_input = "what is the weather " * 5000
        cls, conf, _ = _run(classify(long_input))
        assert cls == "weather"
        assert conf == "High"

    def test_unicode_input(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result("GREETING", 0.90, 0.50)
        cls, conf, _ = _run(classify("こんにちは"))
        assert cls == "greeting"

    def test_strip_system_markers_empty(self):
        assert _strip_system_markers("") == ""

    def test_strip_system_markers_whitespace(self):
        result = _strip_system_markers("   ")
        assert result == "   "

    def test_end_conversation_regex_no_catastrophic_backtracking(self):
        evil = "ok " * 500 + "x"
        import time
        start = time.monotonic()
        _end_conversation_phrase_ok(evil)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"Regex took {elapsed:.2f}s — possible catastrophic backtracking"

    def test_force_stage3_regex_no_catastrophic_backtracking(self):
        evil = "think " + "a " * 500
        import time
        start = time.monotonic()
        _FORCE_STAGE3_RE.search(evil)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"Regex took {elapsed:.2f}s — possible catastrophic backtracking"

    def test_subject_change_only_strips_once(self):
        double = "change the subject to change the subject to weather"
        result = _strip_system_markers(double)
        assert "change the subject to weather" in result


# ---------------------------------------------------------------------------
# 12. CONTRACT 5 — class name exhaustiveness
# ---------------------------------------------------------------------------

class TestContract5ClassNameExhaustiveness:
    """Every value _CLASS_MAP can return must exist in the pipeline class registry."""

    def test_all_class_map_values_have_class_pack(self):
        unique_values = set(_CLASS_MAP.values())
        for name in unique_values:
            dir_name = name.replace(" ", "_")
            pack_dir = CLASSES_DIR / dir_name
            assert pack_dir.is_dir(), (
                f"Pipeline name {name!r} (dir={dir_name!r}) has no class pack. "
                f"Stage 2 will silently fall through to Stage 3."
            )

    def test_all_class_map_chromadb_names_are_uppercase(self):
        for key in _CLASS_MAP:
            assert key == key.upper(), (
                f"_CLASS_MAP key {key!r} should be uppercase to match ChromaDB convention"
            )

    def test_all_class_map_pipeline_names_are_lowercase(self):
        for key, val in _CLASS_MAP.items():
            assert val == val.lower(), (
                f"_CLASS_MAP[{key!r}] = {val!r} should be lowercase to match pipeline registry"
            )

    @pytest.mark.parametrize("raw_cls,expected_pipeline", list(_CLASS_MAP.items()))
    def test_class_map_produces_correct_pipeline_name(self, raw_cls, expected_pipeline, mock_stage1):
        if raw_cls in ("DELEGATE_OPUS", "FORCE_STAGE3"):
            pytest.skip("These always route to 'others' regardless")
        mock_stage1.return_value = _mock_classify_result(raw_cls, confidence=1.0, margin=1.0)
        prompt = "test prompt"
        if raw_cls == "END_CONVERSATION":
            prompt = "goodbye"
        elif raw_cls in STRICT_CLASSES:
            keywords = _STRICT_KEYWORDS.get(raw_cls, ())
            prompt = f"show me my {keywords[0] if keywords else 'stuff'}"
        elif raw_cls == "CLINIC_SCHEDULES_INFO":
            prompt = "clinic patient schedule"
        cls, _, _ = _run(classify(prompt))
        assert cls == expected_pipeline


# ---------------------------------------------------------------------------
# 13. GATE THRESHOLD INVARIANTS
# ---------------------------------------------------------------------------

class TestGateThresholdInvariants:
    def test_strict_gate_requires_unanimity(self):
        assert _GATE_STRICT["conf"] == 1.0

    def test_new_gate_at_least_080(self):
        assert _GATE_NEW["conf"] >= 0.80

    def test_proven_gate_lower_than_new(self):
        assert _GATE_PROVEN["conf"] < _GATE_NEW["conf"]

    def test_all_gates_have_positive_margin(self):
        for gate in (_GATE_NEW, _GATE_PROVEN, _GATE_STRICT):
            assert gate["margin"] > 0

    def test_end_conversation_in_proven_still_has_080_floor(self, mock_stage1):
        assert "END_CONVERSATION" in PROVEN_CLASSES
        gate = _gate_for("END_CONVERSATION")
        assert gate == _GATE_PROVEN
        mock_stage1.return_value = _mock_classify_result(
            "END_CONVERSATION", confidence=0.65, margin=0.25
        )
        _, conf, _ = _run(classify("bye"))
        assert conf == "Low", (
            "END_CONVERSATION must be demoted below 0.80 even though PROVEN gate is 0.60"
        )


# ---------------------------------------------------------------------------
# 14. FORCE_STAGE3_PHRASES coverage
# ---------------------------------------------------------------------------

class TestForceStage3PhraseCoverage:
    def test_all_phrases_are_lowercase(self):
        for phrase in FORCE_STAGE3_PHRASES:
            assert phrase == phrase.lower(), f"FORCE_STAGE3 phrase {phrase!r} must be lowercase"

    def test_no_duplicate_phrases(self):
        assert len(FORCE_STAGE3_PHRASES) == len(set(FORCE_STAGE3_PHRASES))

    def test_regex_covers_think_variations(self):
        assert _FORCE_STAGE3_RE.search("think about it deeply")
        assert _FORCE_STAGE3_RE.search("reason it through")
        assert _FORCE_STAGE3_RE.search("ponder this carefully")

    def test_regex_does_not_false_positive(self):
        assert not _FORCE_STAGE3_RE.search("I think it will rain")
        assert not _FORCE_STAGE3_RE.search("the reason is simple")
        assert not _FORCE_STAGE3_RE.search("ponder the meaning of life")


# ---------------------------------------------------------------------------
# 15. AMBIGUOUS PROMPTS — end_conversation must not fire
# ---------------------------------------------------------------------------

class TestAmbiguousPromptsEndConversation:
    """Contract 5: Generate ambiguous prompts; verify end_conversation doesn't fire."""

    AMBIGUOUS_PROMPTS = [
        "Can you stop playing music?",
        "That's enough about the weather",
        "I'm done with my shopping list, now what about dinner?",
        "Forget about the timer, set a new one",
        "Thanks for the weather, now play some music",
        "All set with the playlist, what's the time?",
        "Never mind the email, check my calendar instead",
        "Drop the current topic and tell me a joke",
        "I'm good on that, but what about tomorrow's forecast?",
        "OK great, now send a message to mom",
        "Cancel the timer please and set a new one for 10 minutes",
        "Stop talking about the weather and play jazz",
        "Enough with the jokes, read my messages",
        "Nah, not that song, play something else",
        "Skip it, I want to hear the news instead",
        "I'm done editing my shopping list, show it to me",
        "Leave it alone, let's move on to something else",
        "That's all for emails, what about texts?",
        "We're done with that conversation topic, switch to cooking",
        "No thanks on the reminder, just tell me the time",
    ]

    @pytest.mark.parametrize("prompt", AMBIGUOUS_PROMPTS)
    def test_ambiguous_prompt_does_not_trigger_end_conversation(self, prompt):
        assert not _end_conversation_phrase_ok(prompt), (
            f"Ambiguous prompt should NOT match end_conversation regex: {prompt!r}"
        )


# ---------------------------------------------------------------------------
# 16. VALID END PHRASES — comprehensive regex coverage
# ---------------------------------------------------------------------------

class TestEndConversationRegexCoverage:
    """Ensure the regex matches all documented ending phrases."""

    @pytest.mark.parametrize("phrase", [
        "we're done", "were done", "okay we're done",
        "I'm done", "ok I'm done", "okay i'm done",
        "all done", "ok all done",
        "that's all", "that is all", "that's it", "that is it",
        "ok that's all",
        "thank you", "thanks", "thanks jane", "thank you jane",
        "thanks bye", "thanks goodbye", "thanks that's all",
        "goodbye", "bye", "bye jane", "bye now",
        "see you later", "see ya later", "see ya",
        "talk later", "talk to you later",
        "goodnight", "goodnight jane", "good night", "night jane",
        "night night",
        "end conversation", "end chat", "conversation over", "close conversation",
        "stop", "stop listening", "stop talking", "stop that", "stop right there",
        "cancel", "cancel that", "cancel it", "dismiss",
        "be quiet", "quiet", "shut up", "silence", "shush",
        "enough", "that's enough",
        "nevermind", "never mind", "forget it", "forget about it",
        "drop it", "abort",
        "no thanks", "nope", "nah", "not now", "skip it",
        "go away", "leave me alone",
        "I'm good", "all good", "we're good", "all set",
        "ok cool", "ok great", "ok thanks", "ok thanks bye", "ok done",
        "roger", "roger that done", "over and out",
    ])
    def test_end_phrase_matches(self, phrase):
        assert _end_conversation_phrase_ok(phrase), f"Should match: {phrase!r}"


# ---------------------------------------------------------------------------
# 17. STRICT CLASS → CLASSIFY full integration
# ---------------------------------------------------------------------------

class TestStrictClassIntegration:
    """Strict classes must require both unanimous votes AND keyword match."""

    @pytest.mark.parametrize("strict_cls", list(STRICT_CLASSES))
    def test_strict_class_needs_unanimous_and_keyword(self, strict_cls, mock_stage1):
        keywords = _STRICT_KEYWORDS[strict_cls]
        prompt_with_keyword = f"please show me {keywords[0]}"
        mock_stage1.return_value = _mock_classify_result(strict_cls, 1.0, 0.50)
        _, conf, _ = _run(classify(prompt_with_keyword))
        assert conf == "High"

    @pytest.mark.parametrize("strict_cls", list(STRICT_CLASSES))
    def test_strict_class_fails_without_keyword(self, strict_cls, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(strict_cls, 1.0, 0.50)
        _, conf, _ = _run(classify("any updates from yesterday"))
        assert conf == "Low"

    @pytest.mark.parametrize("strict_cls", list(STRICT_CLASSES))
    def test_strict_class_fails_below_unanimous(self, strict_cls, mock_stage1):
        keywords = _STRICT_KEYWORDS[strict_cls]
        prompt_with_keyword = f"show {keywords[0]}"
        mock_stage1.return_value = _mock_classify_result(strict_cls, 0.80, 0.30)
        _, conf, _ = _run(classify(prompt_with_keyword))
        assert conf == "Low"


# ---------------------------------------------------------------------------
# 18. MARGIN GATE — below-margin demotes even high confidence
# ---------------------------------------------------------------------------

class TestMarginGate:
    def test_proven_class_high_conf_low_margin_is_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "WEATHER", confidence=0.90, margin=0.10
        )
        _, conf, _ = _run(classify("what's the weather"))
        assert conf == "Low"

    def test_new_class_high_conf_low_margin_is_low(self, mock_stage1):
        mock_stage1.return_value = _mock_classify_result(
            "SHOPPING_LIST", confidence=0.90, margin=0.20
        )
        _, conf, _ = _run(classify("add milk to shopping list"))
        assert conf == "Low"
