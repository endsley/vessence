from context_builder.v1 import context_builder
from context_builder.v1.user_background import (
    PERSONAL_FACTS_FILE,
    _format_fact_snippet,
    _load_personal_facts,
    _select_user_background,
)


def test_load_personal_facts_returns_dict_or_empty(tmp_path):
    assert _load_personal_facts(tmp_path) == {}

    path = tmp_path / PERSONAL_FACTS_FILE
    path.write_text("[1, 2, 3]")
    assert _load_personal_facts(tmp_path) == {}

    path.write_text('{"always": [{"label": "Name", "value": "Chieh"}]}')
    assert _load_personal_facts(tmp_path) == {
        "always": [{"label": "Name", "value": "Chieh"}],
    }


def test_format_fact_snippet_requires_label_and_value():
    assert _format_fact_snippet({"label": " Name ", "value": " Chieh "}) == "Name: Chieh"
    assert _format_fact_snippet({"label": "", "value": "Chieh"}) == ""
    assert _format_fact_snippet({"label": "Name", "value": ""}) == ""


def test_select_user_background_includes_always_and_matching_topic_groups_once():
    personal_facts = {
        "always": [
            {"label": "Name", "value": "Chieh"},
            {"label": "Music", "value": "Piano"},
            "ignored",
        ],
        "topic_map": {
            "ai_coding": [
                {"label": "Stack", "value": "Python"},
                {"label": "Name", "value": "Chieh"},
            ],
            "music": [{"label": "Music", "value": "Piano"}],
            "teaching": [{"label": "Teaching", "value": "DS3000"}],
        },
    }

    assert _select_user_background("debug the Python lecture code", personal_facts) == (
        "Name: Chieh\n"
        "Music: Piano\n"
        "Stack: Python\n"
        "Teaching: DS3000"
    )


def test_context_builder_reexports_user_background_helpers():
    assert context_builder.PERSONAL_FACTS_FILE == PERSONAL_FACTS_FILE
    assert context_builder._load_personal_facts is _load_personal_facts
    assert context_builder._select_user_background is _select_user_background
