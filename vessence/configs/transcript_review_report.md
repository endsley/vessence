# Transcript Quality Review — 2026-05-20

Generated: 2026-05-21 01:14:24

## Issue 1 [CRITICAL]

**Turn:** 2026-05-20 01:10:50
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up reply was not routed through pending_action_resolver and then produced no response.

**Root cause:** The utterance is clearly a continuation answer, but the pipeline went directly to Stage 1 as others:Low with no resolver log. It then escalated to Stage 3, where brain streaming failed and no final response payload was emitted.

**Suggested fix:** Persist pending_action state across the prior turn and add resolver entry/exit logging before Stage 1. If resolver state is absent for short affirmative/parameter replies, route to a clarification fallback instead of generic Stage 3. Also make stage3_escalate return a user-visible fallback when brain streaming errors.

**Log evidence:**
```
2026-05-20 01:10:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2403ms) params={}
```
```
2026-05-20 01:10:50 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:10:50 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:10:50 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-20 01:11:03
**User said:** currently how does your short-term memory work

**Problem:** Complex memory question escalated correctly but Stage 3 failed with no response.

**Root cause:** Stage 1 classified the turn as others:Low, which is reasonable for a system-memory explanation. The OpenAI brain stream then failed, and the proxy exited without a final response payload.

**Suggested fix:** Fix the OpenAI brain streaming failure path and add exception detail to jane.proxy logs. stage3_escalate should emit a fallback response instead of ending the stream empty.

**Log evidence:**
```
2026-05-20 01:11:03 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1066ms) params={}
```
```
2026-05-20 01:11:03 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=46 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:11:03 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:11:03 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-20 01:11:07
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a greeting

**Problem:** Prompt-injection-looking text was misclassified as greeting and loaded the greeting class protocol.

**Root cause:** Stage 1 returned greeting:Very High for literal class_protocol text rather than treating it as arbitrary user text or unsafe protocol injection. The greeting handler then returned an invalid shape, causing escalation with class_protocol=loaded:greeting.

**Suggested fix:** Add a pre-classification sanitizer/rule that treats literal '<class_protocol' and similar runtime-instruction tags in user text as untrusted content and blocks class protocol loading. Fix greeting handler to always return the expected response schema.

**Log evidence:**
```
2026-05-20 01:11:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (867ms) params={}
```
```
2026-05-20 01:11:06 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-20 01:11:06 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```
```
2026-05-20 01:11:07 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-05-20 01:11:09
**User said:** it seems to me that you are no longing making any sounds when speech to text is turned back on

**Problem:** Audio/STT diagnostic request escalated correctly but Stage 3 failed with no response.

**Root cause:** Stage 1 classified the troubleshooting request as others:Low and escalated. The brain stream failed, then the proxy exited without a final payload. No Android diagnostic events were present to support client-side analysis.

**Suggested fix:** Repair Stage 3 streaming and include Android voice_flow/tool_handler diagnostics in the audit log bundle for voice-client issues. Add a deterministic diagnostics handler for STT/audio complaints if this is a common support intent.

**Log evidence:**
```
2026-05-20 01:11:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (974ms) params={}
```
```
2026-05-20 01:11:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:11:09 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:11:09 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-05-20 01:11:12
**User said:** can you look at the short-term memory to see if this whole thing is actually being done observe it through our current turn

**Problem:** Memory-inspection request escalated correctly but Stage 3 failed with no response.

**Root cause:** The classifier sent the request to others:Low, appropriate for a complex introspection/debug request. Stage 3 failed during brain streaming and emitted no final payload.

**Suggested fix:** Fix the Stage 3 brain stream backend and add a deterministic short-term-memory debug handler for requests that need live memory inspection.

**Log evidence:**
```
2026-05-20 01:11:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (823ms) params={}
```
```
2026-05-20 01:11:12 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=123 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:11:12 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:11:12 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-05-20 01:11:15
**User said:** __debug_inspect_update_short_term_memory

**Problem:** Internal debug command was not handled deterministically and Stage 3 failed.

**Root cause:** The pipeline classified the explicit debug command as others:Low instead of routing it to a debug handler. Escalation to Stage 3 failed during streaming and returned no final payload.

**Suggested fix:** Add a Stage 1 rule or pre-router for reserved debug commands such as __debug_inspect_update_short_term_memory, with a deterministic handler that returns structured inspection output.

**Log evidence:**
```
2026-05-20 01:11:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (745ms) params={}
```
```
2026-05-20 01:11:14 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=40 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:11:15 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:11:15 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-20 01:11:19
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** Project-inspection request escalated correctly but Stage 3 failed with no response.

**Root cause:** Stage 1 classified the code/project request as others:Low, which should route to the frontier brain. The OpenAI stream failed and the proxy finished without a final response payload.

**Suggested fix:** Fix the Stage 3 brain execution failure and add a user-visible fallback when persistent Codex/OpenAI streaming cannot start. Include traceback/error codes in jane.proxy logging.

**Log evidence:**
```
2026-05-20 01:11:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2172ms) params={}
```
```
2026-05-20 01:11:18 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=68 sid_override=True class_protocol=n/a
```
```
2026-05-20 01:11:19 ERROR [jane.proxy] [audit-177925] Brain execution failed (stream)
```
```
2026-05-20 01:11:19 WARNING [jane.proxy] [audit-177925] Stream finished without final response payload
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-05-20 02:30:11
**User said:** session cleanup for audit-177925

**Problem:** Persistent Codex sessions failed to end repeatedly after the failed conversation.

**Root cause:** The proxy logged repeated failures ending persistent Codex sessions, including multiple entries for audit-177925. This likely left stale session resources after Stage 3 stream failures.

**Suggested fix:** Make persistent session cleanup idempotent and log the concrete exception/session state. Add cleanup retry with backoff and remove duplicate cleanup attempts for the same session id.

**Log evidence:**
```
2026-05-20 02:30:11 ERROR [jane.proxy] [audit-177925] Failed to end persistent Codex session
```
```
2026-05-20 02:30:11 ERROR [jane.proxy] [audit-177925] Failed to end persistent Codex session
```
```
2026-05-20 02:30:11 ERROR [jane.proxy] [audit-177925] Failed to end persistent Codex session
```

---

