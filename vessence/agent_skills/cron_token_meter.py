#!/usr/bin/env python3
"""Minimal token usage telemetry for cron-executed LLM calls."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _is_enabled() -> bool:
    flag = os.environ.get("CRON_TOKEN_METER")
    if flag is None:
        return False
    return str(flag).strip().lower() not in {"", "0", "false", "off", "no"}


def _job_id() -> str:
    return (
        os.environ.get("CRON_JOB")
        or os.environ.get("CRON_JOB_NAME")
        or os.environ.get("JOB_NAME")
        or Path(sys.argv[0]).name
    )


def _log_path() -> Path:
    base = os.environ.get(
        "CRON_TOKEN_METER_FILE",
        str(
            Path(os.environ.get("VESSENCE_DATA_HOME", "/tmp")).expanduser()
            / "logs" / "System_log" / "cron_llm_usage.jsonl"
        ),
    )
    path = Path(base).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _estimate_tokens(chars: int) -> int:
    return max(0, (max(0, int(chars)) + 3) // 4)


def log_llm_call(
    *,
    provider: str,
    model: str | None,
    prompt_chars: int,
    response_chars: int,
    elapsed_ms: int,
    success: bool,
    phase: str = "llm_call",
    job: str | None = None,
    error: str | None = None,
) -> None:
    if not _is_enabled():
        return

    try:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "epoch": time.time(),
            "job": job or _job_id(),
            "provider": provider,
            "model": model or "",
            "phase": phase,
            "prompt_chars": int(prompt_chars),
            "response_chars": int(response_chars),
            "prompt_tokens_est": _estimate_tokens(prompt_chars),
            "response_tokens_est": _estimate_tokens(response_chars),
            "elapsed_ms": int(elapsed_ms),
            "success": bool(success),
            "error": (error or "")[:300],
        }
        with _log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
