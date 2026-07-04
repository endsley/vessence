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
