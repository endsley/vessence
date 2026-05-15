# Transcript Quality Review — 2026-05-14

Generated: 2026-05-15 01:37:38

## Issue 1 [MEDIUM]

**Turn:** 2026-05-14 01:10:56
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up reply was not resolved by the pending-action path and was treated as a fresh `others` turn

**Root cause:** This utterance is context-dependent, but the pipeline still ran Stage 1 and escalated directly to Stage 3. The logs show no pending-action interception before classification, so the follow-up resolver did not claim the turn.

**Suggested fix:** Run pending-action resolution before Stage 1 on every turn, persist pending-action metadata until consumed, and add explicit resolver hit/miss logs.

**Log evidence:**
```
2026-05-14 01:10:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1137ms) params={}
```
```
2026-05-14 01:10:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-14 01:10:56 INFO [jane.proxy] [audit-177873] Standing brain turn 1 — injected recent history only
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-14 01:14:36
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling 

**Problem:** Stage 1 misclassified user-supplied protocol text as `greeting` with Very High confidence

**Root cause:** The classifier appears to have latched onto the injected `<class_protocol name="greeting">` text and selected the greeting class. Stage 3 then loaded the greeting class protocol, meaning raw user content was allowed to steer protocol selection.

**Suggested fix:** Sanitize or strip control-like markup before classification, add adversarial tests for protocol-looking payloads, and require semantic validation before loading any class protocol.

**Log evidence:**
```
2026-05-14 01:14:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (880ms) params={}
```
```
2026-05-14 01:14:35 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-14 01:14:36
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling 

**Problem:** The greeting fast-path handler failed its contract and returned an invalid shape

**Root cause:** After the misclassification to `greeting`, the deterministic Stage 2 handler did not return a valid response object, forcing an unnecessary Stage 3 fallback.

**Suggested fix:** Make the greeting handler schema-safe for malformed inputs and fall back to a canned greeting response instead of emitting an invalid handler result.

**Log evidence:**
```
2026-05-14 01:14:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (880ms) params={}
```
```
2026-05-14 01:14:35 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-05-14 01:15:42
**User said:** it seems to me that you are no longing making any sounds when speech to text 

**Problem:** Stage 3 took over 5 minutes to answer a runtime problem report

**Root cause:** The request escalated to Stage 3, the standing brain was restarted again because it had been spawned locked, the short-term extractor timed out after 45s, and the turn still did not complete for 322545ms.

**Suggested fix:** Stop respawning the standing brain on routine unlocked turns, move short-term extraction off the critical path, and enforce a hard Stage 3 response SLA with graceful fallback.

**Log evidence:**
```
2026-05-14 01:15:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-14 01:15:42 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-14 01:16:25 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-14 01:21:06 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 322545ms (617 chars, 3 raw events)
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-14 01:21:10
**User said:** can you look at the short-term memory to see if this whole thing is actually 

**Problem:** A live short-term-memory inspection request went through slow Stage 3 while the memory extractor itself timed out

**Root cause:** The user explicitly asked to inspect short-term memory during the current turn, but the request was handled as generic `others`, sent to Stage 3, and the `short_term_extractor` failed after 45s during the same request.

**Suggested fix:** Add a deterministic debug/introspection handler for memory-inspection requests and make short-term-memory extraction observable without depending on a long-running LLM call.

**Log evidence:**
```
2026-05-14 01:21:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (855ms) params={}
```
```
2026-05-14 01:21:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=123 sid_override=True class_protocol=n/a
```
```
2026-05-14 01:21:52 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-14 01:23:25 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 134226ms (1880 chars, 7 raw events)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-05-14 01:26:50
**User said:** I'm currently are you able to see that the website Jane version is not workin

**Problem:** Stage 1 produced unsupported class `restart server` for a website-failure report

**Root cause:** The classifier explicitly returned an unknown label, `restart server`, which the pipeline then demoted to `others`. This shows classifier label drift or a prompt mismatch with the registered intent set.

**Suggested fix:** Constrain classifier output to the registered classes only and add regression cases for troubleshooting/report-a-problem utterances.

**Log evidence:**
```
2026-05-14 01:26:48 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'restart server' → others
```
```
2026-05-14 01:26:48 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (917ms) params={}
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-05-14 01:29:18
**User said:** is stage 3 brain back up by now

**Problem:** A simple brain-status query was misrouted through Stage 3, and the status endpoint being checked returned 404

**Root cause:** The classifier emitted unsupported class `force stage3`, which fell back to `others`, and soon after the system hit `/api/brain/status` and got a 404. The logs show there was no working deterministic status path for this question.

**Suggested fix:** Add a registered `brain_status` intent/handler backed by a valid health endpoint, and remove or restore stale `/api/brain/status` callers.

**Log evidence:**
```
2026-05-14 01:29:17 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-14 01:29:17 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (797ms) params={}
```
```
2026-05-14 01:29:33 INFO [jane.web] GET /api/brain/status → 404 (2ms)
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-05-14 01:30:34
**User said:** is the stage 3 brain working now

**Problem:** The repeated brain-status query never completed because the client disconnected and the Stage 3 run was cancelled

**Root cause:** Again the classifier emitted unsupported `force stage3` and the request fell through to Stage 3. The system again hit a 404 on `/api/brain/status`, then the client disconnected after about 21s and the brain execution was cancelled before the answer could be delivered.

**Suggested fix:** Answer brain-status requests in Stage 2 using a working health check, and surface timeout/cancellation feedback immediately instead of letting the Stage 3 stream die silently.

**Log evidence:**
```
2026-05-14 01:30:33 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-14 01:30:47 INFO [jane.web] GET /api/brain/status → 404 (1ms)
```
```
2026-05-14 01:30:55 INFO [jane.proxy] [audit-177873] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-05-14 01:30:56 WARNING [jane.proxy] [audit-177873] Brain execution cancelled (stream) after 21009ms — likely client disconnect or timeout. Stack:
```

---

