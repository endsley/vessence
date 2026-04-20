---
Title: Audit Android chat_error: TransientServerError
Priority: 2
Status: superseded
Superseded-by: job_076_android_streaming_chat_resilience.md
Created: 2026-04-20
Auto-generated: true
Source: android_chat_error_hook
---

## Problem
An Android `chat_error` diagnostic landed on the server. Jane's streaming
chat caught an exception and surfaced a broken reply to the user. Every
occurrence opens an audit job per Chieh's directive.

## Incident

- **Timestamp:** 2026-04-19T16:02:12.815Z
- **Exception:** `com.vessences.android.data.model.TransientServerError`
- **Message:** `Jane is restarting, please try again in a moment`
- **APK:** v0.2.59 (code 290)
- **From voice:** true
- **First app frame:** `com.vessences.android.data.repository.ChatRepository.streamChat` at `Unknown Source:204`

## Stack trace

```
com.vessences.android.data.model.TransientServerError: Jane is restarting, please try again in a moment
	at com.vessences.android.data.repository.ChatRepository.streamChat(Unknown Source:204)
	at X3.e0.invokeSuspend(Unknown Source:844)
	at o4.a.resumeWith(Unknown Source:8)
	at F4.G.run(Unknown Source:112)
	at com.google.common.util.concurrent.s.run(Unknown Source:144)
	at M4.k.run(Unknown Source:2)
	at M4.a.run(Unknown Source:95)

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
