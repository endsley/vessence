"""Pure text helpers for Jane proxy orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jane_web.client_tool_markers import extract_tool_results, format_tool_results_for_brain
from jane_web.stage3_injections import strip_stage3_injections


@dataclass(frozen=True)
class PhoneToolMessagePrep:
    cleaned_message: str
    user_visible_message: str
    brain_visible_message: str
    tool_results: list[dict[str, Any]]
    result_block: str


def prepare_phone_tool_message(message: str | None) -> PhoneToolMessagePrep:
    """Strip phone-tool result markers and build user/brain-visible variants."""
    cleaned_message, tool_results = extract_tool_results(message or "")
    user_visible_message = strip_stage3_injections(cleaned_message)
    result_block = format_tool_results_for_brain(tool_results) if tool_results else ""
    brain_visible_message = (
        f"{result_block}\n\n{cleaned_message}" if result_block else cleaned_message
    )
    return PhoneToolMessagePrep(
        cleaned_message=cleaned_message,
        user_visible_message=user_visible_message,
        brain_visible_message=brain_visible_message,
        tool_results=tool_results,
        result_block=result_block,
    )


def message_for_persistence(message: str, file_context: str | None) -> str:
    base = (message or "").strip()
    if not file_context:
        return base
    return f"{base}\n\n{file_context}".strip()


def progress_snapshot(request_ctx: Any, summary_text: str, file_context: str | None) -> str:
    findings: list[str] = []
    if summary_text:
        findings.append("loaded prior conversation summary")
    if "## Retrieved Memory\n" in request_ctx.system_prompt:
        findings.append("found relevant memory")
    if "## Current Task State\n" in request_ctx.system_prompt:
        findings.append("loaded task state")
    if "## Research Brief\n" in request_ctx.system_prompt:
        findings.append("prepared research brief")
    if file_context:
        findings.append("attached file context")
    if not findings:
        return "Context is ready."
    return "Context is ready: " + ", ".join(findings) + "."
