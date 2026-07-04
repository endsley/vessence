from types import SimpleNamespace

from jane_web.proxy_text import (
    message_for_persistence,
    prepare_phone_tool_message,
    progress_context_findings,
    progress_snapshot,
)


def test_message_for_persistence_trims_message_and_appends_file_context():
    assert message_for_persistence(" hello ", None) == "hello"
    assert message_for_persistence(" hello ", "") == "hello"
    assert message_for_persistence("", " file context ") == "file context"
    assert message_for_persistence("hello", "file context") == "hello\n\nfile context"


def test_prepare_phone_tool_message_keeps_plain_message_variants_identical():
    prepared = prepare_phone_tool_message("hello")

    assert prepared.cleaned_message == "hello"
    assert prepared.user_visible_message == "hello"
    assert prepared.brain_visible_message == "hello"
    assert prepared.tool_results == []
    assert prepared.result_block == ""


def test_prepare_phone_tool_message_prepends_tool_results_for_brain_only():
    prepared = prepare_phone_tool_message(
        '[TOOL_RESULT:{"tool":"messages.fetch_unread","status":"ok",'
        '"message":"Done","data":{"count":2}}] what changed?'
    )

    assert prepared.cleaned_message == "what changed?"
    assert prepared.user_visible_message == "what changed?"
    assert prepared.tool_results == [
        {
            "tool": "messages.fetch_unread",
            "status": "ok",
            "message": "Done",
            "data": {"count": 2},
        }
    ]
    assert prepared.result_block.startswith("[PHONE TOOL RESULTS")
    assert prepared.brain_visible_message == f"{prepared.result_block}\n\nwhat changed?"


def test_prepare_phone_tool_message_strips_stage3_injections_from_user_visible_only():
    prepared = prepare_phone_tool_message("<class_protocol>secret</class_protocol>\n\nhello")

    assert prepared.cleaned_message == "<class_protocol>secret</class_protocol>\n\nhello"
    assert prepared.user_visible_message == "hello"
    assert prepared.brain_visible_message == "<class_protocol>secret</class_protocol>\n\nhello"


def test_progress_snapshot_returns_default_when_no_context_loaded():
    request_ctx = SimpleNamespace(system_prompt="plain prompt")

    assert progress_snapshot(request_ctx, "", None) == "Context is ready."


def test_progress_snapshot_lists_findings_in_existing_order():
    request_ctx = SimpleNamespace(
        system_prompt=(
            "## Retrieved Memory\nfacts\n"
            "## Current Task State\nstate\n"
            "## Research Brief\nbrief"
        )
    )

    assert progress_snapshot(request_ctx, "summary", "file") == (
        "Context is ready: loaded prior conversation summary, found relevant memory, "
            "loaded task state, prepared research brief, attached file context."
    )


def test_progress_context_findings_preserves_detection_order():
    assert progress_context_findings(
        "## Current Task State\nstate\n## Retrieved Memory\nfacts",
        "summary",
        "file",
    ) == [
        "loaded prior conversation summary",
        "found relevant memory",
        "loaded task state",
        "attached file context",
    ]
