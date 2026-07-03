"""Pure request/result formatting helpers for web_search_utils.py."""

from __future__ import annotations

from typing import Any


TAVILY_QUOTA_STATUSES = {402, 429}


def tavily_request_payload(api_key: str, query: str, max_results: int) -> dict[str, Any]:
    return {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }


def is_tavily_quota_status(status_code: int) -> bool:
    return status_code in TAVILY_QUOTA_STATUSES


def format_tavily_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    parts = []
    for result in results:
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        parts.append(f"[{title}]({url})\n{content}")
    return "\n\n".join(parts)


def format_ddg_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    parts = []
    for result in results:
        title = result.get("title", "")
        href = result.get("href", "")
        body = result.get("body", "")
        parts.append(f"[{title}]({href})\n{body}")
    return "\n\n".join(parts)
