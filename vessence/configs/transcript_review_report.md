# Transcript Quality Review — 2026-05-04

Generated: 2026-05-05 01:26:15

## Issue 1 [CRITICAL]

**Turn:** 2026-05-04 01:06:38
**User said:** I want them to periodically get the lead after some time

**Problem:** Stage 3 dropped the turn and returned no final response.

**Root cause:** The request escalated out of Stage 1, but the Claude stream failed in the proxy and the pipeline exited without emitting any fallback payload, so the user received no answer.

**Suggested fix:** In the Stage 3 proxy/escalation path, catch stream failures and always return a final error payload or retry result instead of allowing the stream to end without a response.

**Log evidence:**
```
2026-05-04 01:06:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1212ms) params={}
```
```
2026-05-04 01:06:38 ERROR [jane.proxy] [audit-177787] Brain execution failed (stream)
```
```
2026-05-04 01:06:38 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-04 01:06:40
**User said:** yes those articles and maybe just two days

**Problem:** A follow-up reply was not routed by the pending-action resolver; it was treated as a fresh `others` request and then dropped.

**Root cause:** This utterance is an elliptical answer to a prior question, but it still went through Stage 1 and was classified `others:Low` instead of bypassing classification. After that miss, Stage 3 also failed and produced no final response.

**Suggested fix:** Persist pending-action state from Stage 2/Stage 3 follow-up questions and route short affirmative/parameter-only replies directly to the owning handler before classification.

**Log evidence:**
```
2026-05-04 01:06:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1140ms) params={}
```
```
2026-05-04 01:06:40 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-04 01:06:40 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-04 01:06:43
**User said:** currently how does your short-term memory work

**Problem:** Stage 3 dropped the turn and returned no final response.

**Root cause:** Stage 1 escalated the request appropriately, but the Claude stream failed and the proxy closed the stream without a final payload.

**Suggested fix:** Add a guaranteed fallback response on Stage 3 stream failure and trip a temporary health gate after repeated `Brain execution failed (stream)` events.

**Log evidence:**
```
2026-05-04 01:06:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (786ms) params={}
```
```
2026-05-04 01:06:43 ERROR [jane.proxy] [audit-177787] Brain execution failed (stream)
```
```
2026-05-04 01:06:43 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-05-04 01:06:46
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling

**Problem:** Classifier prompt-injection misrouted the turn to `greeting`, the greeting handler returned an invalid shape, and the request then failed in Stage 3.

**Root cause:** Stage 1 labeled the injected protocol text as `greeting:Very High`; the pipeline explicitly logged that the `greeting` handler returned an invalid shape and escalated. Stage 3 then failed and produced no final response.

**Suggested fix:** Strip or neutralize user-supplied protocol/XML blocks before classification, ignore literal class-contract text as intent evidence, and enforce handler response schemas with tests so invalid shapes cannot reach production.

**Log evidence:**
```
2026-05-04 01:06:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (727ms) params={}
```
```
2026-05-04 01:06:45 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-04 01:06:46 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-05-04 01:06:49
**User said:** it seems to me that you are no longing making any sounds when speech to text 

**Problem:** Stage 3 dropped the diagnostic turn and returned no final response.

**Root cause:** The request escalated from Stage 1, but the proxy logged a Stage 3 stream failure and then ended without a final payload.

**Suggested fix:** Return a deterministic outage/apology response when the brain stream fails, instead of leaving the client with no assistant reply.

**Log evidence:**
```
2026-05-04 01:06:48 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (718ms) params={}
```
```
2026-05-04 01:06:49 ERROR [jane.proxy] [audit-177787] Brain execution failed (stream)
```
```
2026-05-04 01:06:49 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-05-04 01:06:52
**User said:** can you look at the short-term memory to see if this whole thing is actually 

**Problem:** Stage 3 dropped the turn and returned no final response.

**Root cause:** After Stage 1 classified the request as `others:Low`, the proxy's Claude stream failed and no final response payload was emitted.

**Suggested fix:** Add a fallback response path for Stage 3 failures and alert on repeated stream failures within the same session.

**Log evidence:**
```
2026-05-04 01:06:51 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (861ms) params={}
```
```
2026-05-04 01:06:52 ERROR [jane.proxy] [audit-177787] Brain execution failed (stream)
```
```
2026-05-04 01:06:52 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-04 01:06:54
**User said:** __debug_inspect_update_short_term_memory

**Problem:** Stage 3 dropped the turn and returned no final response.

**Root cause:** The proxy again logged `Brain execution failed (stream)` and then closed without a final payload, so even the debug-style command produced no answer.

**Suggested fix:** Implement a hard error response for failed Stage 3 streams and consider a dedicated deterministic handler for internal debug commands.

**Log evidence:**
```
2026-05-04 01:06:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (711ms) params={}
```
```
2026-05-04 01:06:54 ERROR [jane.proxy] [audit-177787] Brain execution failed (stream)
```
```
2026-05-04 01:06:54 WARNING [jane.proxy] [audit-177787] Stream finished without final response payload
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-05-04 10:03:39
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** The request escalated to Stage 3, but the brain was unavailable and the user received no response.

**Root cause:** The web layer logged `Init session failed` shortly before the turn. The request then went to Stage 3, where the Claude stream failed and the proxy finished without a final payload.

**Suggested fix:** Gate Stage 3 escalation on successful session initialization and return a deterministic 'brain unavailable' response or auto-restart before accepting the turn.

**Log evidence:**
```
2026-05-04 10:03:12 ERROR [jane.web] Init session failed
```
```
2026-05-04 10:03:39 ERROR [jane.proxy] [b7bcba8dcdd3] Brain execution failed (stream)
```
```
2026-05-04 10:03:39 WARNING [jane.proxy] [b7bcba8dcdd3] Stream finished without final response payload
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-05-04 10:15:11
**User said:** I'm currently are you able to see that the website Jane version is not working

**Problem:** Stage 1 emitted an unsupported class (`restart server`), fell back to `others`, and the turn still failed in Stage 3 with no reply.

**Root cause:** The classifier log shows Qwen producing an unknown label, which the pipeline coerced to `others:Low`. At the same time the web layer had `Init session failed`, and the subsequent Stage 3 stream died without a final payload.

**Suggested fix:** Constrain classifier outputs to the registered class set with server-side validation/re-prompting, and short-circuit to a user-visible outage message when session init or Stage 3 startup has failed.

**Log evidence:**
```
2026-05-04 10:15:09 ERROR [jane.web] Init session failed
```
```
2026-05-04 10:15:10 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'restart server' → others
```
```
2026-05-04 10:15:11 WARNING [jane.proxy] [jane_android] Stream finished without final response payload
```

---

## Issue 10 [CRITICAL]

**Turn:** 2026-05-04 10:22:20
**User said:** is stage 3 brain back up by now

**Problem:** A Stage-3-status question was classified through unsupported `force stage3`, then routed into a Stage 3 backend that was still down.

**Root cause:** The classifier again emitted an unknown label and fell back to `others`. The request hit Stage 3 and failed at 10:22:20, while the standing brain was only started at 10:22:25, so the status check itself raced the recovery.

**Suggested fix:** Add a deterministic Stage 2 health/status handler for 'is Stage 3 up' queries and block Stage 3 escalation until the standing brain is confirmed ready.

**Log evidence:**
```
2026-05-04 10:22:18 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-04 10:22:20 WARNING [jane.proxy] [jane_android] Stream finished without final response payload
```
```
2026-05-04 10:22:25 INFO [jane.standing_brain] Standing brain started: provider=claude model=claude-opus-4-6 pid=924260
```

---

## Issue 11 [MEDIUM]

**Turn:** 2026-05-04 15:59:07
**User said:** is the stage 3 brain working now

**Problem:** The turn eventually succeeded, but the first post-unlock Stage 3 request incurred a 33-second recovery delay.

**Root cause:** The standing brain had been spawned while the vault was locked. The system only noticed and restarted it after this user turn arrived, so the request blocked on recovery before completion.

**Suggested fix:** When vault lock state changes, eagerly respawn or rehydrate the standing brain in the background so the next user turn does not pay the restart penalty.

**Log evidence:**
```
2026-05-04 15:59:07 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-04 15:59:40 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 32066ms (210 chars, 2 raw events)
```
```
2026-05-04 15:59:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (33483ms)
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-05-04 23:12:25
**User said:** can you mute my computer for me

**Problem:** A simple action request incurred another avoidable Stage 3 cold-start because the standing brain was still in the wrong lock state.

**Root cause:** The same locked/unlocked mismatch reappeared later that day. The request entered Stage 3, triggered another standing-brain restart, and took 11.5 seconds end-to-end instead of using a warm brain.

**Suggested fix:** Persist the corrected brain state after unlock or continuously reconcile vault state so later turns do not repeatedly restart the standing brain.

**Log evidence:**
```
2026-05-04 23:12:25 INFO [jane.proxy] [jane_android] Standing brain turn 1 — injected recent history only
```
```
2026-05-04 23:12:25 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-04 23:12:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (11532ms)
```

---

