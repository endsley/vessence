"""Structured FIFO record builders for Jane v2/v3 conversation context."""

from __future__ import annotations

from typing import Any


def non_null_items(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def client_tool_result_records(client_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.get("name") or tool.get("tool"),
            "args": tool.get("args", {}),
        }
        for tool in client_tools
    ]


def fifo_metadata_from_extras(extras: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if extras.get("conversation_end"):
        metadata["conversation_end"] = True
    if extras.get("evidence"):
        metadata["evidence"] = extras["evidence"]
    return metadata


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
        record.update(non_null_items(handler_structured))
    if extras:
        if extras.get("client_tools"):
            record.setdefault("tool_results", []).extend(client_tool_result_records(extras["client_tools"]))
        metadata = fifo_metadata_from_extras(extras)
        if metadata:
            record.setdefault("metadata", {}).update(metadata)
    return record
