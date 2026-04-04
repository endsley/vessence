#!/usr/bin/env python3
"""
web_search_utils.py — Shared web search with Tavily-first, DuckDuckGo fallback.

Uses Tavily when TAVILY_API_KEY is set and quota remains.
Falls back to DuckDuckGo on quota exhaustion (HTTP 429/402) or any Tavily error.
"""
import sys
import os
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH, TAVILY_API_KEY

load_dotenv(ENV_FILE_PATH)

logger = logging.getLogger('web_search')


def web_search(query: str, max_results: int = 6) -> str:
    """
    Search the web. Tries Tavily first; falls back to DuckDuckGo.
    Returns a formatted string of results, or empty string on total failure.
    """
    if TAVILY_API_KEY:
        result = _tavily_search(query, max_results)
        if result is not None:
            return result
        logger.warning("Tavily failed or quota exhausted — falling back to DuckDuckGo")

    return _ddg_search(query, max_results)


def _tavily_search(query: str, max_results: int) -> str | None:
    """Returns formatted results string, or None if quota/error."""
    try:
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=15,
        )
        if resp.status_code in (402, 429):
            logger.warning(f"Tavily quota exhausted (HTTP {resp.status_code})")
            return None
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return ""
        parts = []
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            parts.append(f"[{title}]({url})\n{content}")
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"Tavily error: {e}")
        return None


def _ddg_search(query: str, max_results: int) -> str:
    """DuckDuckGo fallback."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        parts = []
        for r in results:
            title = r.get("title", "")
            href = r.get("href", "")
            body = r.get("body", "")
            parts.append(f"[{title}]({href})\n{body}")
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"DuckDuckGo error: {e}")
        return ""
