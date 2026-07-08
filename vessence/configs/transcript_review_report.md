# Transcript Quality Review — 2026-07-07

Generated: 2026-07-08 01:37:18

## Issue 1 [CRITICAL]

**Turn:** 2026-07-07 01:19:00
**User said:** use the source code as your guide

**Problem:** Stage 3 follow-up lost the prior conversational context.

**Root cause:** The turn was a direct follow-up to the previous question, but Stage 3 was invoked with history=0, so the brain had no prior message context to interpret what source code should guide.

**Suggested fix:** Ensure stage3_escalate passes the session conversation history for the sid, or preserve a pending contextual follow-up when the prior Stage 3 response asks or implies continuation.

**Log evidence:**
```
2026-07-07 01:18:59 INFO [jane.proxy] [audit-178340] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```
```
2026-07-07 01:18:59 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-07 01:20:41
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 took 147 seconds for a project-familiarization request.

**Root cause:** The request correctly escalated to Stage 3, but the end-to-end latency was 147342ms, which is too slow for normal interactive use.

**Suggested fix:** Add progress streaming or a bounded codebase-summary path for project-familiarization requests, and avoid blocking the full response on expensive exploratory work.

**Log evidence:**
```
2026-07-07 01:20:41 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-07-07 01:23:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (147342ms)
```

---

## Issue 3 [LOW]

**Turn:** 2026-07-07 01:23:16
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers,

**Problem:** Stage 1 classifier produced an unsupported label.

**Root cause:** The classifier returned 'web automation', which is not a recognized class, so the pipeline coerced it to others. Escalation was acceptable, but the classifier vocabulary/protocol is drifting.

**Suggested fix:** Constrain classifier output to the canonical enum with schema validation or map 'web automation' to the appropriate supported category before logging it as unknown.

**Log evidence:**
```
2026-07-07 01:23:14 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-07 01:23:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2570ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-07-07 01:23:16
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers,

**Problem:** Stage 3 ran for nearly seven minutes on a coding task before finishing.

**Root cause:** Stage 3 handled the request, but the pipeline end-to-end time was 414710ms. During the run, memory extraction also timed out on primary and fallback LLMs, adding background failures/noise.

**Suggested fix:** Separate nonessential memory extraction from the response critical path, add progress events for long coding tasks, and set clearer task execution timeouts or continuation behavior.

**Log evidence:**
```
2026-07-07 01:23:15 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-07-07 01:23:59 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-07-07 01:24:44 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-07-07 01:25:01 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI (claude) failed (exit 1): Failed to authenticate. API Error: 401 Invalid authentication credentials
```
```
2026-07-07 01:30:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (414710ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-07 01:30:42
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 was cancelled after the client disconnected, so the self-heal task did not complete.

**Root cause:** The task escalated correctly, but Stage 3 ran for 462069ms until the client disconnected or timed out, then brain execution was cancelled.

**Suggested fix:** Run long self-heal/code tasks as durable background jobs decoupled from the client stream, with job status polling and resumable output instead of cancelling brain execution on stream disconnect.

**Log evidence:**
```
2026-07-07 01:30:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-07-07 01:38:24 INFO [jane.proxy] [audit-178340] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-07 01:38:24 WARNING [jane.proxy] [audit-178340] Brain execution cancelled (stream) after 462069ms — likely client disconnect or timeout. Stack:
```
```
2026-07-07 01:38:24 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (462914ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-07-07 01:30:42
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 1 classification latency was excessive.

**Root cause:** The classifier took 10565ms to classify a turn that ultimately went to others:Low and Stage 3. That delay is user-visible before any useful work begins.

**Suggested fix:** Add a classifier timeout/fallback threshold for long or structured task prompts, routing directly to Stage 3 when the input exceeds a length or complexity threshold.

**Log evidence:**
```
2026-07-07 01:30:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (10565ms) params={}
```
```
2026-07-07 01:30:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```

---

