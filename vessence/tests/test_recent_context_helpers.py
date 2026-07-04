from jane_web.jane_v2 import recent_context


def test_recent_context_budget_keeps_newest_valid_lines_and_drops_oldest() -> None:
    lines = ["old", "", "middle", {"bad": "line"}, "newest"]

    assert recent_context._recent_context_lines_within_budget(lines, max_chars=12) == [
        "newest"
    ]
    assert recent_context._recent_context_lines_within_budget(lines, max_chars=0) == [
        "newest"
    ]


def test_recent_context_cloud_redaction_preserves_class_placeholder() -> None:
    assert recent_context._redact_summary_for_cloud(
        {"privacy": "local_only", "intent": "send_message", "summary": "secret"}
    ) == "[private turn — class: send_message]"
    assert recent_context._redact_summary_for_cloud({"summary": "visible"}) == "visible"
