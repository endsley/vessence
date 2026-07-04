from jane_web import task_classifier
from jane_web.task_classifier import (
    _has_code_references,
    _pattern_score,
    classify_task,
    strip_bg_prefix,
)


def test_task_classifier_uses_compiled_followup_regex():
    assert task_classifier._FOLLOWUP_STARTERS_RE.match("please go ahead")


def test_task_classifier_pattern_and_code_reference_helpers():
    assert _pattern_score(task_classifier._quick_re, "what is this?") == 2
    assert _pattern_score(task_classifier._quick_re, "implement the change") == 0
    assert _has_code_references("update `main.py` and styles.css")
    assert not _has_code_references("update the docs")


def test_classify_task_forces_background_prefix_and_strips_prefix():
    message = "background: what is the current state of the project?"

    assert classify_task(message) == "big"
    assert strip_bg_prefix(message) == "what is the current state of the project?"
    assert strip_bg_prefix(" bg: do it ") == "do it"


def test_classify_task_keeps_followup_messages_quick():
    long_followup = "please go ahead and " + ("implement that change carefully. " * 10)

    assert classify_task(long_followup) == "quick"


def test_classify_task_keeps_questions_quick_even_when_long():
    question = (
        "Can you explain how the jane_web stream handler works, including how "
        "it handles dedupe, status messages, and final responses?"
    )

    assert classify_task(question) == "quick"


def test_classify_task_marks_compound_implementation_request_big():
    request = (
        "Please refactor the upload handling across the module, then add tests "
        "for the helper boundaries, and finally run the relevant focused suite."
    )

    assert classify_task(request) == "big"
