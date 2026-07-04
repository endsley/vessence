"""Announcement message helpers for task_offloader.py."""

from __future__ import annotations


def truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def start_progress_message(message: str) -> str:
    return f"⏳ Working on your request in the background…\n\n> {truncate_text(message, 200)}"


def heartbeat_progress_message(last_delta: str) -> str | None:
    snippet = last_delta[-300:] if last_delta else ""
    if not snippet:
        return None
    return f"⏳ Still working… (latest output)\n\n```\n{snippet}\n```"


def empty_response_retry_message() -> str:
    return "⏳ Got an empty response — retrying…"


def final_result_message(result: str | None) -> str:
    return result or "_(task completed with no output)_"


def automation_error_category(error_text: str) -> str:
    lowered = error_text.lower()
    if "timed out" in lowered:
        return "timeout"
    if "empty response" in lowered:
        return "empty_response"
    if "not found" in lowered:
        return "not_found"
    if "exit code" in lowered:
        return "exit_code"
    return "generic"


def automation_error_user_message(error_text: str) -> str:
    category = automation_error_category(error_text)
    if category == "timeout":
        return "The request timed out — the AI took too long to respond. Try a simpler request or try again later."
    if category == "empty_response":
        return "The AI returned an empty response after retrying. This usually means the model is overloaded — please try again in a minute."
    if category == "not_found":
        return "The AI backend is not available right now. Please try again later."
    if category == "exit_code":
        return f"The AI backend encountered an error: {error_text[:300]}"
    return f"Background task failed: {error_text[:300]}"


def automation_error_announcement_message(error_text: str) -> str:
    return f"⚠️ {automation_error_user_message(error_text)}"


def unexpected_error_announcement_message(exc: Exception) -> str:
    return f"⚠️ An unexpected error occurred: {type(exc).__name__}: {str(exc)[:200]}"
