"""chat_error_audit.py — auto-generate audit jobs from Android chat_error diagnostics.

When the Android app POSTs a `chat_error` diagnostic (a streaming exception
like SocketException "software caused connection abort"), we drop a job
spec into configs/job_queue/ so the next `run job queue:` picks it up.

Per Chieh's directive: every chat_error opens a normal-priority job.
Deduplication intentionally omitted — if the queue becomes noisy, add
coalescing later.

The job spec includes:
  - exception class, message, stack trace, app version, timestamp
  - the first `com.vessences.android.*` stack frame mapped to its source file
  - a scope section telling the executor to audit that source file,
    identify the root cause, propose a long-term fix, implement if safe
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from pathlib import Path
from typing import Any

from agent_skills.chat_error_audit_helpers import (
    chat_error_job_filename as _chat_error_job_filename,
    chat_error_job_markdown as _chat_error_job_markdown,
    first_android_frame as _parse_first_android_frame,
    slugify_chat_error as _slugify_chat_error,
)

logger = logging.getLogger(__name__)

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
JOB_QUEUE_DIR = VESSENCE_HOME / "configs" / "job_queue"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _next_job_number() -> int:
    """Return 1 + the highest existing job number across active + completed."""
    highest = 0
    for base in (JOB_QUEUE_DIR, JOB_QUEUE_DIR / "completed"):
        if not base.exists():
            continue
        for f in base.glob("job_*.md"):
            m = re.match(r"job_(\d+)_", f.name)
            if m:
                try:
                    highest = max(highest, int(m.group(1)))
                except ValueError:
                    pass
    return highest + 1


def _slugify(s: str, max_len: int = 40) -> str:
    return _slugify_chat_error(s, max_len=max_len)


def _first_android_frame(stack_trace: str) -> dict[str, Any] | None:
    """Parse the stack trace and return the topmost com.vessences.android.* frame.

    Returns {"class_method": str, "file": str, "line": int|None} or None.
    """
    return _parse_first_android_frame(stack_trace)


def _find_source_path(kt_file: str) -> str | None:
    """Best-effort: find the matching .kt/.java source file in the repo."""
    if not kt_file:
        return None
    candidates = list((VESSENCE_HOME / "android").rglob(kt_file))
    if not candidates:
        return None
    # Prefer paths under main/java/com/vessences/android/
    ranked = sorted(
        candidates,
        key=lambda p: 0 if "main/java/com/vessences" in str(p) else 1,
    )
    return str(ranked[0].relative_to(VESSENCE_HOME))


def create_audit_job(payload: dict) -> Path | None:
    """Create a job_NNN_chat_error_*.md spec from a chat_error diagnostic.

    `payload` is the JSON body POSTed by the Android app to
    /api/device-diagnostics. Expected keys: timestamp, category, message,
    exception_class, stack_trace, from_voice, app_version, version_code.

    Returns the created job file path, or None if disabled / on error.
    """
    try:
        JOB_QUEUE_DIR.mkdir(parents=True, exist_ok=True)

        exc_class = payload.get("exception_class", "") or "UnknownException"
        stack = payload.get("stack_trace", "") or ""
        now = _utcnow()
        ts = payload.get("timestamp", "") or now.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        frame = _first_android_frame(stack) or {}
        src_hint = _find_source_path(frame.get("file", "")) or frame.get("file", "")

        num = _next_job_number()
        job_path = JOB_QUEUE_DIR / _chat_error_job_filename(num, exc_class)
        body = _chat_error_job_markdown(
            payload,
            frame=frame,
            source_hint=src_hint,
            created_date=now.strftime("%Y-%m-%d"),
            timestamp=ts,
        )
        job_path.write_text(body)
        logger.info("chat_error_audit: created %s", job_path.name)
        return job_path
    except Exception as e:
        logger.warning("chat_error_audit: failed to create job: %s", e)
        return None
