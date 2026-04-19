"""Batched async persistence for Stage 3 turns.

Replaces three sequential subprocess-based LLM calls (theme classify +
theme summary via `claude CLI haiku`, session summary via qwen python
subprocess) with a single HTTP call to the already-warm Ollama qwen
runner. Runs entirely on the main event loop — no daemon thread, no
fork, no GIL contention during subprocess init.

Design (investigation 2026-04-18):
- Three subprocess forks per Stage 3 turn on a 1.4 GB jane-web process
  stacked up into event-loop stalls of 45-50 s.
- `keep_alive=-1` qwen is free to call — no fork, just HTTP.
- One combined prompt produces BOTH the theme decision AND the session
  summary in a single ~1-2 s warm response.

Call shape:
    result = await update_persistence_batched(
        session_id, user_msg, assistant_msg,
        themes=themes_from_chroma,
        current_summary=current_session_summary,
    )
    # result = {"theme": {...}, "session_topics": [...]}

The caller is responsible for writing the result into ChromaDB and the
session-summary file. This module only does the LLM part.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


_MAX_THEME_TITLE_LEN = 80
_MAX_SUMMARY_LEN = 500
_MAX_SESSION_TOPICS = 3


def _build_prompt(
    themes: list[dict],
    current_session_summary: dict,
    user_msg: str,
    assistant_msg: str,
) -> str:
    themes_block = "\n".join(
        f'  {i}. "{t.get("metadata", {}).get("theme_title", "Untitled")}" — '
        f'{(t.get("document") or "")[:120]}'
        for i, t in enumerate(themes)
    ) or "  (no existing themes)"

    current_topics = json.dumps(
        {"topics": current_session_summary.get("topics", [])[:_MAX_SESSION_TOPICS]},
        ensure_ascii=True,
    )

    return f"""You are updating Jane's short-term memory after a conversation turn. Return ONE JSON object with both a theme decision AND the updated session topics. No prose, no markdown fences.

Existing themes for this session:
{themes_block}

Current session topic state:
{current_topics}

Latest user message:
{user_msg[:1500]}

Latest Jane response:
{assistant_msg[:2500]}

Return EXACTLY this shape:
{{
  "theme": {{
    "action": "existing" | "new",
    "theme_index": <int 0-based, only if action="existing">,
    "title": "<3-8 word theme title, only if action=\\"new\\">",
    "updated_summary": "<1-2 sentence summary of this theme including the new turn; max 400 chars>"
  }},
  "session_topics": [
    {{"topic": "<short label>", "state": "<what is known/decided>", "open_loop": "<next unresolved step or empty>"}}
  ]
}}

Rules:
- Prefer matching an EXISTING theme. Only use "new" if the turn clearly introduces a different subject.
- "session_topics" holds up to 3 durable topics. Merge related updates into existing topics instead of duplicating.
- Omit greetings, filler, and transient chit-chat from session_topics.
- Keep each session_topic field short and concrete (use specific file/system/project names when relevant).

JSON:"""


def _build_body(model: str, prompt_text: str, num_ctx: int, keep_alive: int) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 500,
            "num_ctx": num_ctx,
        },
        "keep_alive": keep_alive,
    }


def update_persistence_batched_sync(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    *,
    themes: list[dict],
    current_session_summary: dict,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any] | None:
    """Sync version — safe to call from a daemon thread without an event loop.

    Uses httpx sync client. The long HTTP wait releases the GIL so the main
    event-loop thread keeps running. No subprocess fork (the whole point of
    this module) so no fork-time GIL block on the 1.4 GB jane-web process.
    """
    try:
        from jane_web.jane_v2.models import (
            LOCAL_LLM as _LOCAL_LLM,
            LOCAL_LLM_NUM_CTX as _NUM_CTX,
            OLLAMA_KEEP_ALIVE as _KEEP_ALIVE,
            OLLAMA_URL as _OLLAMA_URL,
            record_ollama_activity,
        )
    except Exception as e:
        logger.warning("persistence_batch: models import failed: %s", e)
        return None

    model = model or _LOCAL_LLM
    endpoint = ollama_url or _OLLAMA_URL
    prompt_text = _build_prompt(themes, current_session_summary, user_msg, assistant_msg)
    body = _build_body(model, prompt_text, _NUM_CTX, _KEEP_ALIVE)

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(endpoint, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip()
            try:
                record_ollama_activity()
            except Exception:
                pass
    except Exception as e:
        logger.warning(
            "persistence_batch (sync): Ollama call failed (%s) — session=%s",
            e, session_id[:12] if session_id else "?",
        )
        return None

    return _parse_response(session_id, raw, time.perf_counter() - t0)


async def update_persistence_batched(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    *,
    themes: list[dict],
    current_session_summary: dict,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any] | None:
    """Async version for callers already on the event loop."""
    try:
        from jane_web.jane_v2.models import (
            LOCAL_LLM as _LOCAL_LLM,
            LOCAL_LLM_NUM_CTX as _NUM_CTX,
            OLLAMA_KEEP_ALIVE as _KEEP_ALIVE,
            OLLAMA_URL as _OLLAMA_URL,
            record_ollama_activity,
        )
    except Exception as e:
        logger.warning("persistence_batch: models import failed: %s", e)
        return None

    model = model or _LOCAL_LLM
    endpoint = ollama_url or _OLLAMA_URL
    prompt_text = _build_prompt(themes, current_session_summary, user_msg, assistant_msg)
    body = _build_body(model, prompt_text, _NUM_CTX, _KEEP_ALIVE)

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(endpoint, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip()
            try:
                record_ollama_activity()
            except Exception:
                pass
    except Exception as e:
        logger.warning(
            "persistence_batch: Ollama call failed (%s) — session=%s",
            e, session_id[:12] if session_id else "?",
        )
        return None

    return _parse_response(session_id, raw, time.perf_counter() - t0)


def _parse_response(session_id: str, raw: str, elapsed_s: float) -> dict[str, Any] | None:
    latency_ms = int(elapsed_s * 1000)

    # Parse JSON robustly — strip markdown fences, trailing prose.
    cleaned = raw.strip().lstrip("`").rstrip("`").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].lstrip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        logger.warning(
            "persistence_batch: no JSON in response (session=%s, %dms): %r",
            session_id[:12] if session_id else "?", latency_ms, raw[:160],
        )
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(
            "persistence_batch: JSON parse failed (%s, %dms): %r",
            e, latency_ms, cleaned[start:end + 1][:160],
        )
        return None

    theme = parsed.get("theme") or {}
    topics = parsed.get("session_topics") or []

    # Defensive clamping
    if isinstance(theme.get("title"), str):
        theme["title"] = theme["title"][:_MAX_THEME_TITLE_LEN]
    if isinstance(theme.get("updated_summary"), str):
        theme["updated_summary"] = theme["updated_summary"][:_MAX_SUMMARY_LEN]
    topics = [t for t in topics if isinstance(t, dict)][:_MAX_SESSION_TOPICS]

    logger.info(
        "persistence_batch: session=%s %dms action=%s topics=%d",
        session_id[:12] if session_id else "?",
        latency_ms,
        theme.get("action", "?"),
        len(topics),
    )

    return {"theme": theme, "session_topics": topics}
