"""Pure helpers for Android chat_error audit job generation."""

from __future__ import annotations

import re
from typing import Any


FRAME_RE = re.compile(
    r"\s*at\s+(com\.vessences\.android\.[\w\.\$]+)"
    r"\s*\(([^:)]+)(?::(\d+))?\)"
)


def slugify_chat_error(value: str, max_len: int = 40) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").lower()).strip("_")
    return value[:max_len] or "chat_error"


def first_android_frame(stack_trace: str) -> dict[str, Any] | None:
    if not stack_trace:
        return None
    for line in stack_trace.splitlines():
        match = FRAME_RE.search(line)
        if match:
            return {
                "class_method": match.group(1),
                "file": match.group(2),
                "line": int(match.group(3)) if match.group(3) else None,
            }
    return None


def chat_error_job_filename(job_number: int, exception_class: str) -> str:
    exc_short = (exception_class or "UnknownException").rsplit(".", 1)[-1]
    return f"job_{job_number:03d}_{slugify_chat_error(f'chat_error_{exc_short}')}.md"


def chat_error_job_markdown(
    payload: dict[str, Any],
    *,
    frame: dict[str, Any] | None,
    source_hint: str,
    created_date: str,
    timestamp: str,
) -> str:
    exc_class = payload.get("exception_class", "") or "UnknownException"
    exc_short = exc_class.rsplit(".", 1)[-1]
    message = payload.get("message", "") or ""
    stack = payload.get("stack_trace", "") or ""
    app_version = payload.get("app_version", "") or "?"
    version_code = payload.get("version_code", "") or "?"
    from_voice = payload.get("from_voice", "") or ""
    frame = frame or {}
    line_hint = frame.get("line")
    loc = f"{source_hint}:{line_hint}" if source_hint and line_hint else (source_hint or "unknown")
    title = f"Audit Android chat_error: {exc_short}"

    return f"""---
Title: {title}
Priority: 2
Status: pending
Created: {created_date}
Auto-generated: true
Source: android_chat_error_hook
---

## Problem
An Android `chat_error` diagnostic landed on the server. Jane's streaming
chat caught an exception and surfaced a broken reply to the user. Every
occurrence opens an audit job per Chieh's directive.

## Incident

- **Timestamp:** {timestamp}
- **Exception:** `{exc_class}`
- **Message:** `{message[:400]}`
- **APK:** v{app_version} (code {version_code})
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
