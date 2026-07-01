# Transcript Quality Review — 2026-06-30

Generated: 2026-07-01 01:33:33

## Issue 1 [MEDIUM]

**Turn:** 2026-06-30 01:19:35
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 ran far beyond an interactive response window and only finished after about 13 minutes.

**Root cause:** The request correctly escalated to Stage 3, but the frontier brain stream took 798665ms end-to-end. Short-term memory extraction also failed during the run because the primary CLI timed out and both fallbacks failed.

**Suggested fix:** For large coding tasks, route to a background job mode with progress events instead of a normal stream, and make memory extraction non-blocking with a configured working fallback or suppressed retry noise.

**Log evidence:**
```
2026-06-30 01:19:32 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-30 01:19:33 INFO [jane.proxy] [audit-178279] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-30 01:20:17 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-30 01:20:33 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```
```
2026-06-30 01:32:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (798665ms)
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-06-30 01:32:57
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 response was cancelled after the client disconnected, so the task likely produced no usable final answer.

**Root cause:** The brain was still working when the client disconnected, then stream execution was cancelled after 167660ms. The pipeline ended without evidence of a final payload.

**Suggested fix:** Detach long-running Stage 3 coding jobs from the client stream, persist job state/results, and let the client reconnect or poll instead of cancelling the brain task on disconnect.

**Log evidence:**
```
2026-06-30 01:32:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-06-30 01:35:45 INFO [jane.proxy] [audit-178279] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-30 01:35:46 WARNING [jane.proxy] [audit-178279] Brain execution cancelled (stream) after 167660ms — likely client disconnect or timeout. Stack:
```
```
2026-06-30 01:35:46 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (169459ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-30 09:52:20
**User said:** # Task: Waterlily iterative refactor 1/5

**Problem:** Stage 3 job was cancelled after a long run when the client disconnected.

**Root cause:** The request escalated correctly, but the stream ran for 402040ms before client disconnect caused brain cancellation.

**Suggested fix:** Run queued refactor tasks through a durable background worker rather than a streaming request path tied to client lifetime.

**Log evidence:**
```
2026-06-30 09:52:19 INFO [jane.proxy] [job_queue_se] stream_message brain=OpenAI history=0 msg_len=2810 file_ctx=False
```
```
2026-06-30 09:59:02 INFO [jane.proxy] [job_queue_se] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-30 09:59:02 WARNING [jane.proxy] [job_queue_se] Brain execution cancelled (stream) after 402040ms — likely client disconnect or timeout. Stack:
```
```
2026-06-30 09:59:02 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (402778ms)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-06-30 10:00:02
**User said:** # Task: Waterlily iterative refactor 1/5

**Problem:** Stage 3 stream failed after about two hours and returned no final response payload.

**Root cause:** The retry entered Stage 3, ran for 7208888ms, then jane.proxy logged brain execution failed, stream exiting after error, and stream finished without final response payload.

**Suggested fix:** Add a hard per-job timeout with checkpointed progress and an explicit failure response; surface the underlying exception in structured logs so the root runtime error can be diagnosed.

**Log evidence:**
```
2026-06-30 09:59:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=2810 sid_override=True class_protocol=n/a
```
```
2026-06-30 12:00:05 ERROR [jane.proxy] [job_queue_se] Brain execution failed (stream)
```
```
2026-06-30 12:00:05 WARNING [jane.proxy] [job_queue_se] Stream exiting after error event
```
```
2026-06-30 12:00:05 WARNING [jane.proxy] [job_queue_se] Stream finished without final response payload
```
```
2026-06-30 12:00:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (7208888ms)
```

---

## Issue 5 [LOW]

**Turn:** 2026-06-30 12:00:27
**User said:** # Task: Education / teaching app iterative refactor 1/5

**Problem:** Stage 1 classification latency was unusually high for a request that only needed Stage 3 escalation.

**Root cause:** The classifier took 1479ms, then there was a 14-second gap before stage3_escalate logged, indicating slow handoff before the brain started.

**Suggested fix:** Instrument the pipeline segment between Stage 1 completion and stage3_escalate, and skip expensive classifier work for queued task payloads that should always force Stage 3.

**Log evidence:**
```
2026-06-30 12:00:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1479ms) params={}
```
```
2026-06-30 12:00:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=2868 sid_override=True class_protocol=n/a
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-30 12:10:04
**User said:** # Task: Vessence iterative refactor 1/5

**Problem:** Stage 1 was slow, and memory extraction failed during Stage 3.

**Root cause:** The classifier took 5214ms. During Stage 3, short-term memory extraction attempted a CLI primary call, timed out, then failed both gemini and claude fallbacks.

**Suggested fix:** Bypass Stage 1 for job-queue task envelopes and fix the memory extractor fallback configuration so missing CLI tools do not create repeated failed calls.

**Log evidence:**
```
2026-06-30 12:10:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (5214ms) params={}
```
```
2026-06-30 12:10:36 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-30 12:10:53 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI (gemini) failed (exit 1): Loaded cached credentials.
```
```
2026-06-30 12:10:53 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-30 12:10:53 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```

---

