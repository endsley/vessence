"""Pure helpers for save_context_summary.py."""
from __future__ import annotations

import json


def parse_hook_payload(raw: str) -> dict:
    try:
        parsed = json.loads(raw.strip()) if raw.strip() else {}
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def response_text_from_payload(payload: dict) -> str:
    return payload.get("message", "")


def should_summarize_response(response_text: str, *, min_chars: int = 50) -> bool:
    return bool(response_text) and len(response_text.strip()) >= min_chars


def clean_qwen_summary(stdout: str) -> str:
    lines = stdout.strip().splitlines()
    lines = [line for line in lines if not line.startswith("---")]
    return " ".join(lines).strip()


def context_snapshot_fact(timestamp: str, summary: str) -> str:
    return f"[Context snapshot {timestamp}] {summary}"


def last_summary_record(timestamp: str, summary: str) -> dict:
    return {"timestamp": timestamp, "summary": summary}
