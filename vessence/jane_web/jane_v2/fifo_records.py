"""Structured FIFO record builders for Jane v2/v3 conversation context."""

from __future__ import annotations

from typing import Any


def build_fifo_turn_record(
    *,
    user_prompt: str,
    jane_response: str,
    summary: str,
    stage: str = "stage2",
    intent: str = "",
    privacy: str | None = None,
    confidence: str = "",
    handler_structured: dict[str, Any] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "user_text": user_prompt or "",
        "assistant_text": jane_response,
        "summary": summary,
        "stage": stage,
        "intent": intent or "",
    }
    if privacy:
        record["privacy"] = privacy
    if confidence:
        record["confidence"] = confidence
    if handler_structured:
        for key, value in handler_structured.items():
            if value is not None:
                record[key] = value
    if extras:
        if extras.get("client_tools"):
            record.setdefault("tool_results", []).extend(
                [
                    {
                        "name": tool.get("name") or tool.get("tool"),
                        "args": tool.get("args", {}),
                    }
                    for tool in extras["client_tools"]
                ]
            )
        if extras.get("conversation_end"):
            record.setdefault("metadata", {})["conversation_end"] = True
        if extras.get("evidence"):
            record.setdefault("metadata", {})["evidence"] = extras["evidence"]
    return record
