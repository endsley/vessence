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


def chat_error_source_location(frame: dict[str, Any] | None, source_hint: str) -> str:
    frame = frame or {}
    line_hint = frame.get("line")
    return f"{source_hint}:{line_hint}" if source_hint and line_hint else (source_hint or "unknown")


def chat_error_incident_fields(
    payload: dict[str, Any],
    *,
    frame: dict[str, Any] | None,
    source_hint: str,
) -> dict[str, Any]:
    exc_class = payload.get("exception_class", "") or "UnknownException"
    frame = frame or {}
    return {
        "exc_class": exc_class,
        "exc_short": exc_class.rsplit(".", 1)[-1],
        "message": payload.get("message", "") or "",
        "stack": payload.get("stack_trace", "") or "",
        "app_version": payload.get("app_version", "") or "?",
        "version_code": payload.get("version_code", "") or "?",
        "from_voice": payload.get("from_voice", "") or "",
        "class_method": frame.get("class_method", "?"),
        "location": chat_error_source_location(frame, source_hint),
    }


def chat_error_front_matter(title: str, created_date: str) -> str:
    return f"""---
Title: {title}
Priority: 2
Status: pending
Created: {created_date}
Auto-generated: true
Source: android_chat_error_hook
---"""


def chat_error_problem_section() -> str:
    return """## Problem
An Android `chat_error` diagnostic landed on the server. Jane's streaming
chat caught an exception and surfaced a broken reply to the user. Every
occurrence opens an audit job per Chieh's directive."""


def chat_error_incident_section(incident: dict[str, Any], timestamp: str) -> str:
    return f"""## Incident

- **Timestamp:** {timestamp}
- **Exception:** `{incident['exc_class']}`
- **Message:** `{incident['message'][:400]}`
- **APK:** v{incident['app_version']} (code {incident['version_code']})
- **From voice:** {incident['from_voice']}
- **First app frame:** `{incident['class_method']}` at `{incident['location']}`"""


def chat_error_stack_section(stack: str) -> str:
    return f"""## Stack trace

```
{stack[:1800]}
```"""


def chat_error_scope_section() -> str:
    return """## Scope
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
7. Log the outcome via `work_log_tools.log_activity(..., category="chat_error_audit")`."""


def chat_error_verification_section() -> str:
    return """## Verification
- Build APK, install, verify the specific scenario no longer surfaces the
  same exception class + frame.
- If a fix is non-trivial, document the trade-offs in the incident commit."""


def chat_error_notes_section() -> str:
    return """## Notes
- If this is the 5th+ time the same `exception_class` + first frame has
  opened a job, escalate priority and consider a broader redesign rather
  than another point fix.
- Consider whether the Android client should retry instead of surfacing
  the error — but ONLY for reads/idempotent requests. NEVER auto-retry
  `send_message` turns; they may double-send."""


def chat_error_job_markdown(
    payload: dict[str, Any],
    *,
    frame: dict[str, Any] | None,
    source_hint: str,
    created_date: str,
    timestamp: str,
) -> str:
    incident = chat_error_incident_fields(payload, frame=frame, source_hint=source_hint)
    title = f"Audit Android chat_error: {incident['exc_short']}"

    return "\n\n".join([
        chat_error_front_matter(title, created_date),
        chat_error_problem_section(),
        chat_error_incident_section(incident, timestamp),
        chat_error_stack_section(incident["stack"]),
        chat_error_scope_section(),
        chat_error_verification_section(),
        chat_error_notes_section(),
    ]) + "\n"
