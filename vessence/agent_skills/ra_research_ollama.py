"""Ollama request helpers for RA research."""

from __future__ import annotations


def normalize_ollama_base_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/api/generate") or base.endswith("/api/chat"):
        base = base.rsplit("/api/", 1)[0]
    return base


def ollama_chat_payload(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    num_ctx: int,
    temperature: float = 0.1,
) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": num_ctx, "temperature": temperature},
    }
