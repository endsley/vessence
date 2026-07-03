from agent_skills.edu_homework_parsers import (
    lint_displayed_response,
    parse_answer_result,
    parse_client_version,
    parse_prompt_from_question,
)


def test_parse_prompt_and_client_version_from_question_html():
    html = """
    <main>
      <div class="prompt"><p>Solve <strong>x</strong></p></div>
      <input name="client_version" value="7">
    </main>
    """

    raw_html, text = parse_prompt_from_question(html)

    assert "<strong>x</strong>" in raw_html
    assert text == "Solve x"
    assert parse_client_version(html) == 7
    assert parse_client_version('<input name="client_version" value="bad">') == 0
    assert parse_client_version("<main></main>") == 0
    assert parse_prompt_from_question("<p>missing</p>") == ("", "")


def test_parse_answer_result_maps_feedback_classes_and_displayed_response():
    assert parse_answer_result('<div class="feedback ok">Correct.</div>') == {
        "verdict": "correct",
        "feedback_text": "Correct.",
        "displayed_response": None,
    }
    assert parse_answer_result(
        '<div class="feedback warn">already submitted <code>x</code></div>'
    )["verdict"] == "stale"
    assert parse_answer_result(
        '<div class="feedback warn">Attempt locked.</div>'
    )["verdict"] == "locked"
    result = parse_answer_result(
        '<div class="feedback bad">Your answer: <code>vector</code> Incorrect.</div>'
    )
    fallback = parse_answer_result(
        '<div class="feedback bad">You answered <span>near</span> '
        '<code>first</code> and <code>second</code></div>'
    )

    assert result["verdict"] == "incorrect"
    assert result["displayed_response"] == "vector"
    assert fallback["displayed_response"] == "first"
    assert parse_answer_result("<p>missing</p>") == {
        "verdict": "unknown",
        "feedback_text": "",
        "displayed_response": None,
    }


def test_lint_displayed_response_preserves_ui_bug_rules():
    assert lint_displayed_response(None, "[1; 2]", "vector") == []

    answer_type_issue = lint_displayed_response("vector", "[1; 2]", "vector")
    empty_issue = lint_displayed_response("", "[1; 2]", "vector")
    none_issue = lint_displayed_response("(none)", "[1; 2]", "vector")

    assert answer_type_issue[0]["kind"] == "displayed_response_is_answer_type"
    assert empty_issue[0]["kind"] == "displayed_response_empty"
    assert none_issue[0]["kind"] == "displayed_response_none"
