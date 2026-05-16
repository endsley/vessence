# Transcript Quality Review — 2026-05-15

Generated: 2026-05-16 01:31:14

## Issue 1 [CRITICAL]

**Turn:** 2026-05-15 01:14:43
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up reply was not routed through pending_action_resolver and instead went through Stage 1/Stage 3

**Root cause:** The utterance is clearly a continuation/confirmation, but the logs show immediate Stage 1 classification as others:Low and Stage 3 escalation with no pending_action_resolver activity. Stage 3 also received history=0, so the follow-up likely lacked the prior context needed to resolve 'those articles'.

**Suggested fix:** Persist pending_action state across turns and add explicit resolver logging for both hit and miss cases. Before Stage 1, check pending_action for the session and route short confirmation/edit replies directly to the owning handler.

**Log evidence:**
```
2026-05-15 01:14:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1181ms) params={}
```
```
2026-05-15 01:14:43 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-15 01:14:43 INFO [jane.proxy] [audit-177882] stream_message brain=Claude history=0 msg_len=42 file_ctx=False
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-15 01:15:59
**User said:** currently how does your short-term memory work

**Problem:** Stage 3 response path was extremely slow for a normal explanatory question

**Root cause:** The turn escalated correctly to Stage 3, but the brain process was restarted because it had been spawned locked, then the short-term extractor timed out, and the full Stage 3 turn took 126967ms.

**Suggested fix:** Avoid per-turn brain restarts after vault unlock by respawning once and reusing the unlocked process. Move short_term_extractor work fully out of the response critical path or hard-cap it with a shorter nonblocking timeout.

**Log evidence:**
```
2026-05-15 01:15:59 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-15 01:16:31 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-15 01:18:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (126967ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-15 01:18:10
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a greeting

**Problem:** Prompt-injection-like class_protocol text was classified as greeting with Very High confidence

**Root cause:** Stage 1 appears to have trusted the literal '<class_protocol name="greeting">' content in the user message instead of treating it as user text. The greeting handler then returned an invalid shape and forced Stage 3 escalation with class_protocol=loaded:greeting.

**Suggested fix:** Sanitize user text before classification by stripping or escaping internal protocol tags. Add classifier tests for user-supplied '<class_protocol>' payloads and reject handler routing based on embedded protocol markup.

**Log evidence:**
```
2026-05-15 01:18:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (722ms) params={}
```
```
2026-05-15 01:18:08 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-15 01:18:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-15 01:18:10
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a greeting

**Problem:** Greeting handler returned an invalid response shape

**Root cause:** After Stage 1 routed to greeting, the deterministic handler failed its contract and the pipeline had to fall back to Stage 3. This indicates the handler return schema is not being normalized or validated at handler boundaries.

**Suggested fix:** Fix the greeting handler to always return the registered Stage 2 response schema. Add schema validation tests for every deterministic handler and fail closed with a clear internal error instead of silently escalating malformed handler output.

**Log evidence:**
```
2026-05-15 01:18:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (722ms) params={}
```
```
2026-05-15 01:18:08 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-15 01:19:07
**User said:** it seems to me that you are no longing making any sounds when speech to text is

**Problem:** Diagnostic/support turn took over two minutes to answer

**Root cause:** Stage 1 classification as others:Low was reasonable, but Stage 3 restarted the brain again, the short-term extractor timed out, CPU monitoring showed elevated idle CPU, and the turn took 140925ms end-to-end.

**Suggested fix:** Add a fast diagnostic intent/category for voice/audio client issues or provide a lightweight local status response before escalating. Also fix repeated standing-brain restarts and make memory extraction nonblocking.

**Log evidence:**
```
2026-05-15 01:19:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (741ms) params={}
```
```
2026-05-15 01:19:07 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-15 01:19:50 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-15 01:21:28 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (140925ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-05-15 01:19:07
**User said:** it seems to me that you are no longing making any sounds when speech to text is

**Problem:** Client-side audio/STT complaint cannot be verified because Android diagnostic events are missing

**Root cause:** The Android Client Events section is empty, so there are no tool_handler or voice_flow events to confirm whether STT relaunched, audio cues played, or the client suppressed sound.

**Suggested fix:** Ensure the Android client uploads voice_flow and audio cue diagnostic events for every voice turn, including STT start/stop, TTS/audio cue playback attempts, failures, and permission/audio-focus state.

**Log evidence:**
```
## Android Client Events
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-15 01:21:32
**User said:** can you look at the short-term memory to see if this whole thing is actually being done observe

**Problem:** Memory-observation request hung until client disconnect

**Root cause:** The turn escalated to Stage 3, short_term_extractor timed out after 45s, heartbeat pings failed, the brain stayed in elevated-CPU idle monitoring for many minutes, and the stream was cancelled after 789122ms when the client disconnected.

**Suggested fix:** Add a bounded memory diagnostic handler that directly queries short-term memory state and returns within a fixed timeout. Add Stage 3 watchdog cancellation with partial/fallback response, and prevent extractor jobs from contending with live diagnostic turns.

**Log evidence:**
```
2026-05-15 01:21:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1043ms) params={}
```
```
2026-05-15 01:22:15 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-15 01:24:13 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-05-15 01:34:41 INFO [jane.proxy] [audit-177882] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-05-15 01:34:41 WARNING [jane.proxy] [audit-177882] Brain execution cancelled (stream) after 789122ms — likely client disconnect or timeout. Stack:
```
```
2026-05-15 01:34:41 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (789385ms)
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-05-15 03:06:06
**User said:** post-conversation cleanup

**Problem:** Persistent Claude sessions failed to close and memory archival hit database locks/rate limits

**Root cause:** After the audited conversation, multiple persistent Claude sessions failed to end, conversation archival failed because the database was locked, and thematic archival failed due Claude CLI rate limit. This likely contributed to ongoing elevated idle CPU and unreliable memory persistence.

**Suggested fix:** Make persistent session cleanup idempotent with timeout/kill fallback, serialize SQLite archival writes or enable WAL with retry backoff, and queue thematic archival for retry after provider rate-limit reset instead of failing inline.

**Log evidence:**
```
2026-05-15 03:06:06 ERROR [jane.proxy] [audit-177882] Failed to end persistent Claude session
```
```
2026-05-15 03:06:35 WARNING [memory.v1.conversation_manager] Failed to mark session archived: database is locked
```
```
2026-05-15 03:06:50 WARNING [memory.v1.conversation_manager] Thematic archival failed: CLI failed (exit 1): You've hit your limit · resets 6am (America/New_York)
```

---

