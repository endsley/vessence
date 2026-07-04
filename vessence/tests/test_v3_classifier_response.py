import asyncio

import pytest

from intent_classifier.v3 import classifier


def test_handler_name_from_classifier_label_normalizes_chroma_and_pending_labels():
    assert classifier._handler_name_from_classifier_label("TODO_LIST") == "todo list"
    assert classifier._handler_name_from_classifier_label(" Send_Message ") == "send message"
    assert classifier._handler_name_from_classifier_label("") == ""
    assert classifier._handler_name_from_classifier_label(None) == ""


def test_allowed_classifier_classes_preserves_registry_name_normalization():
    registry = {
        "weather": {"name": " Weather "},
        "timer": {"name": "timer"},
        "empty": {"name": ""},
    }

    assert classifier._allowed_classifier_classes(registry) == {"others", "weather", "timer"}


def test_chosen_class_distance_uses_normalized_ranked_labels():
    ranked = [
        {"class": "SHOPPING_LIST", "best_distance": 0.24},
        {"class": "End_Conversation", "best_distance": 0.18},
    ]

    assert classifier._chosen_class_distance(ranked, "shopping list") == 0.24
    assert classifier._chosen_class_distance(ranked, "end conversation") == 0.18
    assert classifier._chosen_class_distance(ranked, "weather") is None


def test_candidate_state_votes_and_normalizes_handlers():
    candidates = [
        {"class": "TIMER", "distance": 0.23},
        {"class": "Weather", "distance": 0.14},
        {"class": "TIMER", "distance": 0.19},
    ]

    state = classifier._candidate_state(candidates)

    assert state == classifier.ClassifierCandidateState(
        candidates=candidates,
        ranked=[
            {"class": "TIMER", "count": 2, "best_distance": 0.19},
            {"class": "Weather", "count": 1, "best_distance": 0.14},
        ],
        winner={"class": "TIMER", "count": 2, "best_distance": 0.19},
        runnerup={"class": "Weather", "count": 1, "best_distance": 0.14},
        winner_handler="timer",
        runnerup_handler="weather",
    )
    assert classifier._candidate_state([]) is None


def test_should_floor_distance_confidence_preserves_exemptions():
    assert classifier._should_floor_distance_confidence(
        conf="High",
        cls="weather",
        chosen_distance=0.23,
        is_pending_choice=False,
        stage2_max_distance=0.22,
    )
    assert not classifier._should_floor_distance_confidence(
        conf="Medium",
        cls="weather",
        chosen_distance=0.23,
        is_pending_choice=False,
        stage2_max_distance=0.22,
    )
    assert not classifier._should_floor_distance_confidence(
        conf="High",
        cls="send message",
        chosen_distance=0.23,
        is_pending_choice=False,
        stage2_max_distance=0.22,
    )
    assert not classifier._should_floor_distance_confidence(
        conf="High",
        cls="weather",
        chosen_distance=0.23,
        is_pending_choice=True,
        stage2_max_distance=0.22,
    )
    assert not classifier._should_floor_distance_confidence(
        conf="High",
        cls="weather",
        chosen_distance=None,
        is_pending_choice=False,
        stage2_max_distance=0.22,
    )


def test_params_for_chosen_class_drops_params_extracted_for_other_schema():
    params = {"recipient": "Chieh"}

    assert classifier._params_for_chosen_class(params, "send message", "send message") == params
    assert classifier._params_for_chosen_class(params, "weather", "send message") == {}
    assert classifier._params_for_chosen_class({}, "weather", "send message") == {}


def test_parse_qwen_classification_response_strips_fences_and_params():
    assert classifier._parse_qwen_classification_response(
        '```json\n{"class": "[Weather]", "confidence": "very high", "params": {"day": "today"}}\n```'
    ) == ("weather", "Very High", {"day": "today"})


def test_parse_qwen_classification_response_extracts_json_from_surrounding_text():
    assert classifier._parse_qwen_classification_response(
        'Reasoning...\n{"class": "todo list", "confidence": "HIGH"}\nDone.'
    ) == ("todo list", "High", {})


def test_parse_qwen_classification_response_falls_back_for_invalid_confidence_and_params():
    assert classifier._parse_qwen_classification_response(
        '{"class": "send message", "confidence": "certain", "params": ["bad"]}'
    ) == ("send message", "Low", {})


def test_parse_qwen_classification_response_returns_none_for_missing_class():
    assert classifier._parse_qwen_classification_response(
        '{"confidence": "High"}'
    ) is None


def test_parse_qwen_classification_response_raises_for_malformed_json():
    with pytest.raises(ValueError):
        classifier._parse_qwen_classification_response("not json")


def test_prompt_candidate_context_uses_chroma_winner_by_default():
    context = classifier._prompt_candidate_context(
        winner_class="weather",
        winner_def="Weather definition",
        runnerup_class="timer",
        runnerup_def="Timer definition",
    )

    assert context == classifier.PromptCandidateContext(
        has_pending=False,
        primary_class="weather",
        primary_def="Weather definition",
        alt_class="timer",
        alt_def="Timer definition",
    )


def test_prompt_candidate_context_swaps_pending_class_to_primary():
    context = classifier._prompt_candidate_context(
        winner_class="shopping list",
        winner_def="Shopping definition",
        runnerup_class="timer",
        runnerup_def="Timer definition",
        pending_class="timer",
        pending_def="Timer pending definition",
    )

    assert context == classifier.PromptCandidateContext(
        has_pending=True,
        primary_class="timer",
        primary_def="Timer pending definition",
        alt_class="shopping list",
        alt_def="Shopping definition",
    )


def test_prompt_candidate_context_does_not_duplicate_same_class_alternative():
    context = classifier._prompt_candidate_context(
        winner_class="timer",
        winner_def="Timer definition",
        runnerup_class="timer",
        runnerup_def="Duplicate timer definition",
        pending_class="Timer",
        pending_def="Timer pending definition",
    )

    assert context == classifier.PromptCandidateContext(
        has_pending=False,
        primary_class="timer",
        primary_def="Timer definition",
        alt_class=None,
        alt_def="",
    )


def test_load_prompt_state_uses_pending_class_schema_when_it_swaps_primary(monkeypatch):
    async def recent_fifo(session_id):
        assert session_id == "sid-1"
        return "jane: What should I call the timer?"

    definitions = {
        "shopping list": "Shopping definition",
        "weather": "Weather definition",
        "timer": "Timer definition",
    }
    schemas = {
        "shopping list": {"item": "item to add"},
        "timer": {"label": "timer label"},
    }

    monkeypatch.setattr(classifier, "_recent_fifo", recent_fifo)
    monkeypatch.setattr(classifier, "_class_definition", lambda name: definitions[name])
    monkeypatch.setattr(classifier, "_class_param_schema", lambda name: schemas.get(name, {}))
    monkeypatch.setattr(
        classifier,
        "_pending_action_class",
        lambda session_id: ("TIMER", "What should I call the timer?"),
    )

    state = asyncio.run(
        classifier._load_prompt_state("sid-1", "shopping list", "weather")
    )

    assert state == classifier.ClassifierPromptState(
        fifo_block="jane: What should I call the timer?",
        winner_def="Shopping definition",
        runnerup_def="Weather definition",
        pending_class="timer",
        pending_def="Timer definition",
        pending_question="What should I call the timer?",
        primary_param_schema={"label": "timer label"},
        schema_class="timer",
    )


def test_prompt_section_helpers_preserve_default_and_pending_prompt_text():
    context = classifier.PromptCandidateContext(
        has_pending=False,
        primary_class="weather",
        primary_def="Weather definition\n\nExamples",
        alt_class="timer",
        alt_def="Timer definition",
    )
    pending = classifier.PromptCandidateContext(
        has_pending=True,
        primary_class="timer",
        primary_def="Timer definition",
        alt_class="shopping list",
        alt_def="Shopping definition",
    )

    assert classifier._prompt_header(context) == (
        "Classify a voice message for Jane. Embedding suggests weather "
        "(runner-up: timer). Validate."
    )
    assert "Judge the SURFACE TEXT" in classifier._prompt_header(pending)
    assert classifier._near_identical_prompt_callout(
        candidate_context=pending,
        winner_best_distance=0.0,
    ) == ""

    callout = classifier._near_identical_prompt_callout(
        candidate_context=context,
        winner_best_distance=0.0,
    )
    assert "prompt embeds near a 'weather' exemplar" in callout
    assert "(d=0.000)" in callout

    classes_block = classifier._prompt_class_blocks(context)
    assert "[weather] Weather definition" in classes_block
    assert "[timer] Timer definition" in classes_block
    assert "[others] neither specific class fits" in classes_block
    assert "[unclear] Pick UNCLEAR only" in classes_block


def test_prompt_context_callout_and_params_instruction_helpers():
    assert classifier._fifo_section("") == "Recent turns: (none)\n"
    assert classifier._fifo_section("jane: Anything else?") == (
        "Recent turns:\njane: Anything else?\n"
    )
    assert classifier._jane_question_callout(
        "jane: What should I call it?",
        "Fallback?",
    ) == "Jane's last question: \"What should I call it?\"\n"
    assert classifier._jane_question_callout("jane: Done.", "Fallback?") == (
        "Jane's last question: \"Fallback?\"\n"
    )

    assert classifier._params_instruction_block("weather", None) == (
        "\nReturn ONLY JSON: "
        "{\"class\": \"<name>\", \"confidence\": \"Very High|High|Medium|Low\"}"
    )
    params_block = classifier._params_instruction_block(
        "weather",
        {"day": "forecast day", "location": "place name"},
    )
    assert "If you classify as weather" in params_block
    assert "  - day: forecast day" in params_block
    assert "  - location: place name" in params_block
    assert '"params": {...}' in params_block
