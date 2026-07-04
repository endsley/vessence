from jane_web import task_offloader
from jane_web.task_offloader_messages import (
    automation_error_announcement_message,
    automation_error_category,
    empty_response_retry_message,
    final_result_message,
    heartbeat_progress_message,
    start_progress_message,
    truncate_text,
    unexpected_error_announcement_message,
)


def test_task_offloader_keeps_legacy_truncate_alias():
    assert task_offloader._truncate is truncate_text


def test_start_and_heartbeat_progress_messages_truncate_and_skip_empty_output():
    assert start_progress_message("x" * 205).startswith(
        "⏳ Working on your request in the background…\n\n> "
    )
    assert start_progress_message("x" * 205).endswith("…")
    assert len(truncate_text("x" * 205, 200)) == 200

    assert heartbeat_progress_message("") is None
    heartbeat = heartbeat_progress_message("a" * 305)
    assert heartbeat == f"⏳ Still working… (latest output)\n\n```\n{'a' * 300}\n```"


def test_retry_and_final_result_messages_preserve_visible_text():
    assert empty_response_retry_message() == "⏳ Got an empty response — retrying…"
    assert final_result_message("done") == "done"
    assert final_result_message("") == "_(task completed with no output)_"
    assert final_result_message(None) == "_(task completed with no output)_"


def test_automation_error_messages_preserve_category_precedence():
    assert automation_error_category("timed out and empty response") == "timeout"
    assert automation_error_category("empty response from model") == "empty_response"
    assert automation_error_category("backend not found") == "not_found"
    assert automation_error_category("exit code 1") == "exit_code"
    assert automation_error_category("other failure") == "generic"

    assert automation_error_announcement_message("timed out after 10s") == (
        "⚠️ The request timed out — the AI took too long to respond. Try a simpler request or try again later."
    )
    assert "empty response after retrying" in automation_error_announcement_message("empty response")
    assert "not available right now" in automation_error_announcement_message("backend not found")
    assert "exit code 1" in automation_error_announcement_message("exit code 1")
    assert automation_error_announcement_message("other failure") == (
        "⚠️ Background task failed: other failure"
    )


def test_unexpected_error_message_preserves_type_and_truncates_text():
    message = unexpected_error_announcement_message(ValueError("x" * 250))

    assert message.startswith("⚠️ An unexpected error occurred: ValueError: ")
    assert message.endswith("x" * 200)
