from jane_web.file_context import resolve_file_context_value


def test_resolve_file_context_prefers_request_payload():
    resolved, source = resolve_file_context_value(
        message="delete it",
        file_context="new file context",
        recent_file_context="old file context",
    )

    assert resolved == "new file context"
    assert source == "request"


def test_resolve_file_context_reuses_recent_context_for_followup_marker():
    resolved, source = resolve_file_context_value(
        message="Can you rename that file?",
        file_context=None,
        recent_file_context="old file context",
    )

    assert resolved == "old file context"
    assert source == "recent"


def test_resolve_file_context_does_not_reuse_recent_context_without_marker():
    resolved, source = resolve_file_context_value(
        message="What is next?",
        file_context=None,
        recent_file_context="old file context",
    )

    assert resolved is None
    assert source == ""


def test_resolve_file_context_preserves_empty_payload_behavior():
    resolved, source = resolve_file_context_value(
        message="delete it",
        file_context="",
        recent_file_context="old file context",
    )

    assert resolved == "old file context"
    assert source == "recent"
