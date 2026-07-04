"""Ollama warmup and heartbeat request helpers for Jane web."""

from __future__ import annotations


def ollama_generate_endpoint(base_url: str) -> str:
    return f"{(base_url or 'http://localhost:11434').rstrip('/')}/api/generate"


def local_llm_prewarm_payload(model: str, num_ctx: int, keep_alive: str | int) -> dict:
    return {
        "model": model,
        "prompt": "hi",
        "stream": False,
        "options": {"num_ctx": num_ctx},
        "keep_alive": keep_alive,
    }


def ollama_heartbeat_payload(model: str, num_ctx: int, keep_alive: str | int) -> dict:
    return {
        "model": model,
        "prompt": ".",
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1,
            "num_ctx": num_ctx,
        },
        "keep_alive": keep_alive,
    }


def heartbeat_poll_seconds(interval_seconds: int) -> int:
    return max(2, interval_seconds // 5)


def should_skip_heartbeat(seconds_since_last_activity: float, interval_seconds: int) -> bool:
    return seconds_since_last_activity < interval_seconds
