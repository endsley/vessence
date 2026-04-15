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

logger = logging.getLogger(__name__)

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
JOB_QUEUE_DIR = VESSENCE_HOME / "configs" / "job_queue"

# Match the first com.vessences.android.* frame in a Java/Kotlin stack trace.
_FRAME_RE = re.compile(
    r"\s*at\s+(com\.vessences\.android\.[\w\.\$]+)"
    r"\s*\(([^:)]+)(?::(\d+))?\)"
)


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
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "").lower()).strip("_")
    return s[:max_len] or "chat_error"


def _first_android_frame(stack_trace: str) -> dict | None:
    """Parse the stack trace and return the topmost com.vessences.android.* frame.

    Returns {"class_method": str, "file": str, "line": int|None} or None.
    """
    if not stack_trace:
        return None
    for line in stack_trace.splitlines():
        m = _FRAME_RE.search(line)
        if m:
            return {
                "class_method": m.group(1),
                "file": m.group(2),
                "line": int(m.group(3)) if m.group(3) else None,
            }
    return None


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
        exc_short = exc_class.rsplit(".", 1)[-1]
        msg = payload.get("message", "") or ""
        stack = payload.get("stack_trace", "") or ""
        ts = payload.get("timestamp", "") or dt.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        app_ver = payload.get("app_version", "") or "?"
        ver_code = payload.get("version_code", "") or "?"
        from_voice = payload.get("from_voice", "") or ""

        frame = _first_android_frame(stack) or {}
        src_hint = _find_source_path(frame.get("file", "")) or frame.get("file", "")
        line_hint = frame.get("line")
        loc = f"{src_hint}:{line_hint}" if src_hint and line_hint else (src_hint or "unknown")

        num = _next_job_number()
        slug = _slugify(f"chat_error_{exc_short}")
        job_path = JOB_QUEUE_DIR / f"job_{num:03d}_{slug}.md"

        title = f"Audit Android chat_error: {exc_short}"

        body = f"""---
Title: {title}
Priority: 2
Status: pending
Created: {dt.datetime.utcnow().strftime("%Y-%m-%d")}
Auto-generated: true
Source: android_chat_error_hook
---

## Problem
An Android `chat_error` diagnostic landed on the server. Jane's streaming
chat caught an exception and surfaced a broken reply to the user. Every
occurrence opens an audit job per Chieh's directive.

## Incident

- **Timestamp:** {ts}
- **Exception:** `{exc_class}`
- **Message:** `{msg[:400]}`
- **APK:** v{app_ver} (code {ver_code})
- **From voice:** {from_voice}
- **First app frame:** `{frame.get("class_method", "?")}` at `{loc}`

## Stack trace

```
{stack[:1800]}
```

## Scope
1. Open the source file identified above (fallback: search the stack trace for
   the first `com.vessences.android.*` frame and navigate to that line).
2. Read the surrounding code and determine whether the exception is:
   - a transient network condition (SocketException, IOException, EOFException)
   - a logic bug (NullPointer, ClassCast, IllegalState)
   - a protocol/contract violation between app and server
3. For transient network conditions: confirm the catch block handles it
   gracefully (user sees a friendly message, state is recoverable, stream
   resumes cleanly). If not, add handling.
4. For logic bugs: fix the root cause. Do NOT add a blanket try/catch unless
   there is no safer alternative.
5. For contract violations: fix both sides (app + server) so the incident
   cannot recur.
6. Write a small test reproducing the failure mode when feasible.
7. Log the outcome via `work_log_tools.log_activity(..., category="chat_error_audit")`.

## Verification
- Build APK, install, verify the specific scenario no longer surfaces the
  same exception class + frame.
- If a fix is non-trivial, document the trade-offs in the incident commit.

## Notes
- If this is the 5th+ time the same `exception_class` + first frame has
  opened a job, escalate priority and consider a broader redesign rather
  than another point fix.
- Consider whether the Android client should retry instead of surfacing
  the error — but ONLY for reads/idempotent requests. NEVER auto-retry
  `send_message` turns; they may double-send.
"""
        job_path.write_text(body)
        logger.info("chat_error_audit: created %s", job_path.name)
        return job_path
    except Exception as e:
        logger.warning("chat_error_audit: failed to create job: %s", e)
        return None
