# Transcript Quality Review — 2026-06-27

Generated: 2026-06-28 01:34:08

## Issue 1 [MEDIUM]

**Turn:** 2026-06-27 01:09:38
**User said:** help pay it

**Problem:** Very short ambiguous request took the slow Stage 3 path instead of a fast clarification.

**Root cause:** Stage 1 classified the 11-character prompt as low-confidence others, then the pipeline escalated directly to Stage 3. There is no quick clarification fallback for incomplete low-confidence utterances.

**Suggested fix:** Add a deterministic clarification response for very short low-confidence others turns, and cap Stage 1 latency with a fast fallback.

**Log evidence:**
```
2026-06-27 01:09:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (5017ms) params={}
```
```
2026-06-27 01:09:38 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=11 sid_override=True class_protocol=n/a
```
```
2026-06-27 01:10:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (30721ms)
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-27 01:12:12
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an out-of-schema intent label.

**Root cause:** The classifier returned 'web automation', which is not a valid class, so the classifier normalized it to others. The final escalation was acceptable, but the classifier contract is drifting.

**Suggested fix:** Constrain Stage 1 output to the allowed enum with strict parsing, and add alias handling or examples for project/web-automation requests.

**Log evidence:**
```
2026-06-27 01:12:10 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-27 01:12:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1054ms) params={}
```

---

## Issue 3 [LOW]

**Turn:** 2026-06-27 01:12:40
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an out-of-schema 'force stage3' intent.

**Root cause:** The classifier generated a routing instruction instead of a valid category. It was normalized to others and escalated, but this indicates the Stage 1 prompt/parser allows invalid labels.

**Suggested fix:** Use strict enum validation with one repair attempt, and add tests that reject meta-routing labels like 'force stage3'.

**Log evidence:**
```
2026-06-27 01:12:38 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-27 01:12:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2151ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-27 01:12:40
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Brain health check endpoint returned 404 during a Stage 3 process-health question.

**Root cause:** The server received GET /api/jane/brain/health while the Stage 3 turn was running, but that route was missing or misconfigured.

**Suggested fix:** Implement /api/jane/brain/health or update the caller to the real health endpoint; include active brain process/session state in the response.

**Log evidence:**
```
2026-06-27 01:13:51 INFO [jane.web] GET /api/jane/brain/health → 404 (37ms)
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-27 01:14:26
**User said:** use the source code as your guide

**Problem:** Context-dependent follow-up was sent to Stage 3 with no explicit history or file context.

**Root cause:** The turn depends on prior Waterlily context, but the proxy invocation shows history=0 and file_ctx=False, and there is no pending_action_resolver routing line in the supplied logs.

**Suggested fix:** For same-session Stage 3 follow-ups, include recent transcript context or preserve a Stage 3 continuation pending_action; log resolver decisions explicitly.

**Log evidence:**
```
2026-06-27 01:14:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1193ms) params={}
```
```
2026-06-27 01:14:25 INFO [jane.proxy] [audit-178253] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-27 01:14:42
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 and memory follow-up were slow, and short-term memory extraction failed.

**Root cause:** The Stage 3 turn took about 298 seconds. Afterward, the short-term extractor exhausted primary, gemini, and claude CLI fallbacks, each timing out after 45 seconds.

**Suggested fix:** Move memory extraction to a bounded async worker, avoid serial 45-second fallback chains on the request path, and retry failed extraction later with the turn id.

**Log evidence:**
```
2026-06-27 01:14:39 INFO [jane.proxy] [audit-178253] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-27 01:19:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (298211ms)
```
```
2026-06-27 01:20:25 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-27 01:21:55 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-06-27 01:20:01
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Large coding request stayed on a long synchronous Stage 3 path.

**Root cause:** The request was correctly escalated, but Stage 3 ran for about 468 seconds in the live pipeline. The classifier also emitted the same out-of-schema 'web automation' label before fallback.

**Suggested fix:** Route long implementation requests to an async job flow with progress updates and final artifact reporting; separately fix the Stage 1 enum/schema drift for web-automation-like requests.

**Log evidence:**
```
2026-06-27 01:19:53 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-27 01:19:54 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-27 01:27:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (467921ms)
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-06-27 02:34:54
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Background self-heal Stage 3 job failed after more than two hours with no final response payload.

**Root cause:** Stage 1 took 22 seconds, then Stage 3 ran for 8000057ms before brain execution failed. The stream exited after an error and explicitly finished without a final response payload.

**Suggested fix:** Add a hard timeout and watchdog for job_queue Stage 3 runs, return a structured failure payload on stream errors, and kill or recycle the stuck brain process before accepting more work.

**Log evidence:**
```
2026-06-27 02:34:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (22068ms) params={}
```
```
2026-06-27 04:47:50 ERROR [jane.proxy] [job_queue_se] Brain execution failed (stream)
```
```
2026-06-27 04:47:54 WARNING [jane.proxy] [job_queue_se] Stream finished without final response payload
```
```
2026-06-27 04:47:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (8000057ms)
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-06-27 02:34:54
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** After the failed self-heal job, server and Codex state became database-locked.

**Root cause:** Multiple Jane web endpoints failed with 'database is locked', and the Standing Brain later failed to start because Codex could not initialize sqlite state under /home/chieh/.codex.

**Suggested fix:** Serialize Codex state access, ensure all sqlite connections are closed on brain failure, enable busy_timeout/WAL where appropriate, and add cleanup/restart logic for stuck app-server state.

**Log evidence:**
```
2026-06-27 05:36:21 ERROR [jane.web] Unhandled error in GET /api/essences after 11719ms: database is locked
```
```
2026-06-27 05:39:49 ERROR [jane.web] Unhandled error in GET /api/essences/active after 24252ms: database is locked
```
```
2026-06-27 08:22:03 ERROR [jane.web] Standing Brain startup failed: Codex app-server stdout closed. Error: failed to initialize sqlite state runtime under /home/chieh/.codex: failed to initialize state runtime at /home/chieh/.codex: error returned from database: (code: 5) database is locked
```

---

