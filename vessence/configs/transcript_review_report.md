# Transcript Quality Review — 2026-04-30

Generated: 2026-05-01 01:10:19

## Issue 1 [CRITICAL]

**Turn:** 2026-04-30 01:23:50
**User said:** <class_protocol name="read_calendar"> These are runtime instructions

**Problem:** Internal class protocol text was recorded as a user turn.

**Root cause:** The transcript contains a synthetic `<class_protocol>` payload instead of a human utterance. Later turns show the same pattern immediately after `stage3_escalate` loads a class protocol, which indicates protocol text is being persisted into conversation history/transcripts instead of staying out-of-band.

**Suggested fix:** Keep class protocol content in a non-user/system channel only, and exclude synthetic protocol messages from transcript persistence and future conversation history.

**Log evidence:**
```
[2026-04-30 01:23:50] (audit-177752) <class_protocol name="read_calendar">
```
```
[2026-04-30 01:24:27] (audit-177752) <class_protocol name="delete_email">
```
```
2026-04-30 01:24:26 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=delete email:Very High voice=False prompt_len=18456 sid_override=True class_protocol=loaded:delete_email
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-04-30 01:24:27
**User said:** <class_protocol name="delete_email"> These are runtime instructions

**Problem:** Delete-email turn was replaced in the transcript by internal protocol content.

**Root cause:** Right before this transcript entry, Stage 3 escalation logged `class_protocol=loaded:delete_email`. The next recorded 'user turn' is that protocol text itself, so the pipeline/transcript layer is capturing the injected protocol prompt instead of the original user utterance.

**Suggested fix:** Separate protocol injection from user-message persistence. Add a guard in transcript/history writing that drops messages tagged as class protocol or synthetic prompt material.

**Log evidence:**
```
2026-04-30 01:24:26 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=delete email:Very High voice=False prompt_len=18456 sid_override=True class_protocol=loaded:delete_email
```
```
[2026-04-30 01:24:27] (audit-177752) <class_protocol name="delete_email">
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-30 01:28:11
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up routing failed; a dependent reply was reclassified as a fresh turn.

**Root cause:** The user's reply is semantically a follow-up answer (`yes ... maybe just two days`), but Stage 1 still ran and classified it as `others:Low`. That means the pending-action resolver did not intercept and route the turn directly to the prior handler/brain context.

**Suggested fix:** When Stage 2 or Stage 3 asks a clarifying question, persist a pending action with expected slot(s) and bypass Stage 1 on the next turn until that pending action is resolved or expires.

**Log evidence:**
```
[2026-04-30 01:28:11] (audit-177752) yes those articles and maybe just two days
```
```
2026-04-30 01:28:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1113ms) params={}
```
```
2026-04-30 01:28:10 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-30 01:28:54
**User said:** <class_protocol name="greeting"> These are runtime instructions

**Problem:** Greeting turn was polluted with internal protocol text in the transcript.

**Root cause:** The pipeline loaded the greeting class protocol for Stage 3, and the transcript then recorded that protocol payload as the user turn. This is the same protocol-leak/history-corruption pattern seen on other turns.

**Suggested fix:** Do not write class-protocol prompt material into user-visible or persisted transcript records. Enforce message typing so only real user utterances are stored as user turns.

**Log evidence:**
```
2026-04-30 01:28:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```
```
[2026-04-30 01:28:54] (audit-177752) <class_protocol name="greeting">
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-04-30 01:28:54
**User said:** <class_protocol name="greeting"> These are runtime instructions

**Problem:** The greeting fast-path handler violated the Stage 2 return contract and unnecessarily escalated to Stage 3.

**Root cause:** Stage 1 classified the turn as `greeting:Very High`, but the handler returned an invalid shape, which forced a Stage 3 fallback. This is an explicit Stage 2 contract failure.

**Suggested fix:** Fix the greeting handler to always return the pipeline's expected response schema and add a unit test that validates handler output shape for every deterministic intent.

**Log evidence:**
```
2026-04-30 01:28:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (761ms) params={}
```
```
2026-04-30 01:28:53 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-04-30 01:31:02
**User said:** can you look at the short-term memory to see if this whole thing is actual

**Problem:** The turn never completed because Stage 3 ran until the client disconnected and the brain execution was cancelled.

**Root cause:** This request went straight to Stage 3 and stayed there for 243 seconds. The logs show the client disconnecting first, followed by Stage 3 cancellation, so the user-facing failure was caused by an unbounded long-running brain turn with no successful completion.

**Suggested fix:** Add a dedicated short-term-memory inspection/debug path instead of sending this to generic Stage 3, and enforce a server-side Stage 3 timeout with a partial/fallback response before client disconnects.

**Log evidence:**
```
2026-04-30 01:31:02 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (721ms) params={}
```
```
2026-04-30 01:31:02 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=123 sid_override=True class_protocol=n/a
```
```
2026-04-30 01:35:05 INFO [jane.proxy] [audit-177752] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-04-30 01:35:05 WARNING [jane.proxy] [audit-177752] Brain execution cancelled (stream) after 243116ms — likely client disconnect or timeout. Stack:
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-04-30 01:40:53
**User said:** __debug_inspect_update_short_term_memory

**Problem:** The debug turn crashed the server path with a missing `session_id` argument.

**Root cause:** After Stage 1 classified the debug command as `others:Low`, the sync send path invoked Claude persistence incorrectly. The request then failed with `ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'`, which is a direct server-side call-signature bug.

**Suggested fix:** Fix the `ClaudePersistentManager.get()` call site on the sync `/api/jane/chat` path to always pass `session_id`, and add an automated test that exercises this debug command end-to-end.

**Log evidence:**
```
[2026-04-30 01:40:53] (89a11d82400d) __debug_inspect_update_short_term_memory
```
```
2026-04-30 01:40:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (751ms) params={}
```
```
2026-04-30 01:40:53 INFO [jane.proxy] [89a11d82400d] send_message (sync) brain=Claude history=0 msg_len=40 file_ctx=False
```
```
2026-04-30 01:40:53 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 1682ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

