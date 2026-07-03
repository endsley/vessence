"""Request timing and prompt dump logging helpers for Jane proxy."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB cap for rotating log files


class ProxyRequestLogger:
    def __init__(
        self,
        request_timing_log: Path,
        prompt_dump_log: Path,
        *,
        perf_counter: Callable[[], float] = time.perf_counter,
        strftime: Callable[[str], str] = time.strftime,
    ):
        self.request_timing_log = request_timing_log
        self.prompt_dump_log = prompt_dump_log
        self.perf_counter = perf_counter
        self.strftime = strftime

    def truncate_log_if_needed(self, log_path: Path) -> None:
        """Truncate a log file to its last 2000 lines if it exceeds LOG_MAX_BYTES."""
        try:
            if log_path.exists() and log_path.stat().st_size > LOG_MAX_BYTES:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                log_path.write_text("\n".join(lines[-2000:]) + "\n", encoding="utf-8")
        except Exception:
            pass

    def log_stage(self, session_id: str, stage: str, start_ts: float, **extra) -> None:
        duration_ms = int((self.perf_counter() - start_ts) * 1000)
        details = " ".join(f"{key}={value}" for key, value in extra.items())
        self.request_timing_log.parent.mkdir(parents=True, exist_ok=True)
        self.truncate_log_if_needed(self.request_timing_log)
        with self.request_timing_log.open("a", encoding="utf-8") as fh:
            fh.write(
                f"{self.strftime('%Y-%m-%d %H:%M:%S')} "
                f"jane_request session={session_id} stage={stage} duration_ms={duration_ms}"
                + (f" {details}" if details else "")
                + "\n"
            )

    def log_start(
        self,
        session_id: str,
        mode: str,
        message: str,
        history_turns: int,
        brain_label: str,
        file_context: str | None,
    ) -> None:
        self.request_timing_log.parent.mkdir(parents=True, exist_ok=True)
        with self.request_timing_log.open("a", encoding="utf-8") as fh:
            fh.write(
                f"{self.strftime('%Y-%m-%d %H:%M:%S')} "
                f"jane_request session={session_id} stage=start mode={mode}"
                f" message_chars={len(message or '')} history_turns={history_turns}"
                f" brain={brain_label} file_context={bool(file_context)}\n"
            )

    def dump_prompt(
        self,
        session_id: str,
        mode: str,
        message: str,
        summary_text: str,
        request_ctx: Any,
        bootstrap_retrieval: bool,
        bootstrap_summary: str,
        file_context: str | None,
    ) -> None:
        self.prompt_dump_log.parent.mkdir(parents=True, exist_ok=True)
        self.truncate_log_if_needed(self.prompt_dump_log)
        record = {
            "timestamp": self.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": session_id,
            "mode": mode,
            "message": message,
            "message_chars": len(message or ""),
            "conversation_summary": summary_text,
            "conversation_summary_chars": len(summary_text or ""),
            "bootstrap_retrieval": bootstrap_retrieval,
            "bootstrap_memory_summary": bootstrap_summary,
            "bootstrap_memory_summary_chars": len(bootstrap_summary or ""),
            "retrieved_memory_summary": request_ctx.retrieved_memory_summary or "",
            "retrieved_memory_summary_chars": len(request_ctx.retrieved_memory_summary or ""),
            "system_prompt": request_ctx.system_prompt or "",
            "system_prompt_chars": len(request_ctx.system_prompt or ""),
            "transcript": request_ctx.transcript or "",
            "transcript_chars": len(request_ctx.transcript or ""),
            "file_context": file_context or "",
        }
        with self.prompt_dump_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
