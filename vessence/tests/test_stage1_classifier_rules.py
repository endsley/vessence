from jane_web.jane_v2 import stage1_classifier as classifier


def test_force_stage3_override_matches_literal_phrase():
    assert (
        classifier._force_stage3_override("Please use stage 3 for this one")
        == "use stage 3"
    )


def test_force_stage3_override_matches_regex_variant():
    assert classifier._force_stage3_override("Think this deeply before answering") == "__regex__"


def test_force_stage3_override_returns_none_without_override():
    assert classifier._force_stage3_override("what is the weather today") is None


def test_classification_confidence_demotes_others_and_delegate_opus():
    assert (
        classifier._classification_confidence("DELEGATE_OPUS", "others", 1.0, 1.0, "answer this")
        == "Low"
    )
    assert (
        classifier._classification_confidence("UNKNOWN_CLASS", "others", 1.0, 1.0, "answer this")
        == "Low"
    )


def test_classification_confidence_requires_strict_keyword():
    assert (
        classifier._classification_confidence("READ_EMAIL", "read email", 1.0, 1.0, "any updates")
        == "Low"
    )
    assert (
        classifier._classification_confidence("READ_EMAIL", "read email", 1.0, 1.0, "check my email")
        == "High"
    )


def test_classification_confidence_rejects_embedded_end_phrase():
    assert (
        classifier._classification_confidence(
            "END_CONVERSATION",
            "end conversation",
            1.0,
            1.0,
            "the context window is not long enough",
        )
        == "Low"
    )


def test_classification_confidence_allows_complete_end_phrase_above_floor():
    assert (
        classifier._classification_confidence("END_CONVERSATION", "end conversation", 0.8, 1.0, "thanks")
        == "High"
    )


def test_classification_confidence_rejects_end_phrase_below_floor():
    assert (
        classifier._classification_confidence("END_CONVERSATION", "end conversation", 0.79, 1.0, "thanks")
        == "Low"
    )


def test_classification_confidence_keeps_personal_schedule_out_of_clinic_class():
    assert (
        classifier._classification_confidence(
            "CLINIC_SCHEDULES_INFO",
            "clinic schedules info",
            1.0,
            1.0,
            "what is my schedule today",
        )
        == "Low"
    )
    assert (
        classifier._classification_confidence(
            "CLINIC_SCHEDULES_INFO",
            "clinic schedules info",
            1.0,
            1.0,
            "what is Kathia's clinic schedule today",
        )
        == "High"
    )


def test_classification_confidence_applies_new_class_gate():
    assert (
        classifier._classification_confidence("TODO_LIST", "todo list", 0.79, 1.0, "add eggs to my todo list")
        == "Low"
    )
    assert (
        classifier._classification_confidence("TODO_LIST", "todo list", 0.8, 0.4, "add eggs to my todo list")
        == "High"
    )
