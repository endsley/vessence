# Transcript Quality Review — 2026-05-19

Generated: 2026-05-20 01:12:28

## Issue 1 [MEDIUM]

**Turn:** 2026-05-19 01:14:15
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up reply was not resolved by pending_action_resolver and fell through to Stage 1/Stage 3.

**Root cause:** The user reply is clearly contextual, but the logs show Stage 1 ran immediately with no resolver log and no pending-action bypass. Stage 3 then handled it with history=0, causing a slow and potentially context-fragile path.

**Suggested fix:** Persist pending_action state across Stage 3 follow-up prompts and add resolver decision logging for every turn, including explicit 'no pending action' entries.

**Log evidence:**
```
2026-05-19 01:14:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1294ms) params={}
```
```
2026-05-19 01:14:15 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-19 01:14:15 INFO [jane.proxy] [audit-177916] stream_message brain=Claude history=0 msg_len=42 file_ctx=False
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-19 01:16:09
**User said:** currently how does your short-term memory work

**Problem:** Stage 3 response path was excessively slow for a direct explanatory question.

**Root cause:** The turn escalated correctly, but the standing Claude brain restarted because it had been spawned while the vault was locked. The turn then took 147384ms end to end.

**Suggested fix:** Fix standing_brain vault-state tracking so an unlocked vault does not trigger a full brain restart on every Stage 3 turn; respawn once after unlock and reuse the process.

**Log evidence:**
```
2026-05-19 01:16:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (835ms) params={}
```
```
2026-05-19 01:16:09 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-19 01:18:36 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (147384ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-19 01:18:39
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a greeting

**Problem:** Prompt-injection-looking text was classified as greeting with Very High confidence and sent to the greeting handler.

**Root cause:** Stage 1 appears to have trusted the embedded class_protocol text rather than treating it as user content. The greeting handler then returned an invalid shape, forcing Stage 3 with class_protocol=loaded:greeting.

**Suggested fix:** Harden Stage 1 against literal protocol/XML-like user text: strip or escape class_protocol blocks before classification, and add an injection/safety fallback category. Also fix the greeting handler to always return the expected response schema.

**Log evidence:**
```
2026-05-19 01:18:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (780ms) params={}
```
```
2026-05-19 01:18:39 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-19 01:18:39 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-19 01:19:36
**User said:** it seems to me that you are no longing making any sounds when speech to text is turned

**Problem:** No Android diagnostic events were captured for a client-side audio/STT complaint.

**Root cause:** The transcript includes an Android/client behavior report, but the Android Client Events section is empty. Stage 3 could only answer from server-side context, not actual tool_handler or voice_flow evidence.

**Suggested fix:** Ensure Android voice_flow and tool_handler diagnostics are uploaded with the same session id and timestamp range whenever voice/STT failures are reported.

**Log evidence:**
```
2026-05-19 01:19:35 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (882ms) params={}
```
```
2026-05-19 01:19:36 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
## Android Client Events
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-19 01:19:36
**User said:** it seems to me that you are no longing making any sounds when speech to text is turned

**Problem:** Stage 3 took 268813ms to answer a troubleshooting report.

**Root cause:** The Stage 3 turn began at 01:19:36 and completed at 01:24:05. During the turn, the short-term extractor also timed out, indicating background LLM work was unhealthy.

**Suggested fix:** Separate background memory extraction from the foreground response path and enforce tighter Stage 3 timeout/streaming progress behavior for voice troubleshooting turns.

**Log evidence:**
```
2026-05-19 01:19:36 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-19 01:20:19 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-19 01:24:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (268813ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-05-19 01:24:09
**User said:** can you look at the short-term memory to see if this whole thing is actually being done

**Problem:** Short-term memory inspection request escalated correctly but the memory subsystem was actively failing.

**Root cause:** The request needed current memory observation, but the short_term_extractor repeatedly timed out around these turns. Stage 3 had no reliable fresh short-term extraction evidence to inspect.

**Suggested fix:** Add a deterministic debug/read path for short-term memory state that does not depend on an LLM extractor call; expose extractor status, last success time, and pending queue depth to Stage 3.

**Log evidence:**
```
2026-05-19 01:24:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (773ms) params={}
```
```
2026-05-19 01:24:52 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-19 01:26:57 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (168125ms)
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-19 01:27:01
**User said:** __debug_inspect_update_short_term_memory

**Problem:** Debug command was routed to Stage 3 instead of a deterministic debug handler.

**Root cause:** Stage 1 classified the explicit debug command as others:Low and escalated to Claude. The follow-up Stage 3 turn ran for 323543ms, while memory extraction continued timing out.

**Suggested fix:** Register '__debug_inspect_update_short_term_memory' as an exact-match internal/debug intent before Stage 1, handled by deterministic code that returns raw memory update state.

**Log evidence:**
```
2026-05-19 01:27:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1033ms) params={}
```
```
2026-05-19 01:27:01 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=40 sid_override=True class_protocol=n/a
```
```
2026-05-19 01:27:43 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-19 01:32:24 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (323543ms)
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-05-19 01:32:34
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** Project/file-system request escalated to Stage 3 with file_ctx=False.

**Root cause:** The user asked Jane to inspect a local project, but the Stage 3 call did not attach file context or evidence of a filesystem-capable tool path. The model could only reply conversationally unless separate tooling existed outside these logs.

**Suggested fix:** Add a local_project/code intent or pre-Stage-3 file context resolver that expands '~', validates the path, and attaches a file context/tool plan before invoking the brain.

**Log evidence:**
```
2026-05-19 01:32:32 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2574ms) params={}
```
```
2026-05-19 01:32:32 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=68 sid_override=True class_protocol=n/a
```
```
2026-05-19 01:32:34 INFO [jane.proxy] [audit-177916] stream_message brain=Claude history=0 msg_len=68 file_ctx=False
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-05-19 02:36:10
**User said:** session cleanup after audit-177916 turns

**Problem:** Persistent Claude sessions failed to terminate repeatedly.

**Root cause:** The proxy logged repeated failures ending persistent sessions, including multiple entries for audit-177916. This likely contributed to later database lock and archival failures.

**Suggested fix:** Make persistent session shutdown idempotent, log the exception details, and add a forced cleanup path for stale Claude processes before archival begins.

**Log evidence:**
```
2026-05-19 02:36:10 ERROR [jane.proxy] [audit-177916] Failed to end persistent Claude session
```
```
2026-05-19 02:36:45 WARNING [memory.v1.conversation_manager] Failed to mark session archived: database is locked
```
```
2026-05-19 02:36:49 WARNING [memory.v1.conversation_manager] Failed to fetch theme registry: database is locked
```

---

