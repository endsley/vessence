from jane_web.jane_v2 import stage2_dispatcher
from jane_web.jane_v2.stage2_dispatcher_prompts import (
    CLASS_DESCRIPTIONS,
    continuation_check_prompt,
    gate_check_prompt,
)


def test_stage2_dispatcher_uses_extracted_prompt_helpers():
    assert stage2_dispatcher._CLASS_DESCRIPTIONS is CLASS_DESCRIPTIONS
    assert stage2_dispatcher._continuation_check_prompt is continuation_check_prompt
    assert stage2_dispatcher._gate_check_prompt is gate_check_prompt
    assert stage2_dispatcher._post_ollama_response.__name__ == "post_ollama_response"


def test_continuation_check_prompt_prefers_literal_pending_question():
    prompt = continuation_check_prompt(
        "todo list",
        "clinic",
        "User: previous\nJane: Which category?",
        pending_question="Which category should I read?",
    )

    assert 'Jane just asked the user this exact question:' in prompt
    assert '"Which category should I read?"' in prompt
    assert "Recent conversation:\nUser: previous" in prompt
    assert "User's reply: clinic" in prompt
    assert prompt.endswith("SAME or CHANGED:")


def test_continuation_check_prompt_uses_class_description_fallback():
    prompt = continuation_check_prompt("weather", "tomorrow", "", pending_question=None)

    assert "the user wants the current/forecast weather" in prompt
    assert "User's reply: tomorrow" in prompt


def test_gate_check_prompt_returns_none_for_unknown_class_and_preserves_examples():
    assert gate_check_prompt("unknown", "hello", "") is None

    prompt = gate_check_prompt("get time", "what time is it", "recent context")
    assert prompt is not None
    assert "The classifier predicted: the user wants the current time" in prompt
    assert '"the time you told me was wrong" → NO (complaint)' in prompt
    assert "Recent conversation:\nrecent context" in prompt
    assert prompt.endswith("Answer ONE word — YES or NO:")
