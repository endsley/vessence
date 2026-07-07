# Transcript Quality Review — 2026-07-06

Generated: 2026-07-07 01:39:08

## Issue 1 [LOW]

**Turn:** 2026-07-06 01:19:08
**User said:** right now, you are using the same codex process for each prompt instead of spawning a

**Problem:** Classifier emitted an unsupported intent label before falling back to others.

**Root cause:** The Stage 1 model returned `force stage3`, which is not in the allowed taxonomy. The pipeline safely mapped it to `others:Low` and escalated, so the user-facing routing was acceptable, but the classifier contract is too loose.

**Suggested fix:** Constrain Stage 1 output to the configured intent enum, or add explicit normalization for known meta labels like `force stage3` before logging them as unknown.

**Log evidence:**
```
2026-07-06 01:19:06 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-06 01:19:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1090ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-06 01:22:39
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 1 classification was extremely slow for a request that only needed Stage 3 escalation.

**Root cause:** The classifier took 37446ms before routing to `others:Low`. Nearby logs show local CLI LLM timeout and fallback/auth failures, suggesting the same overloaded or failing local model stack was delaying auxiliary processing.

**Suggested fix:** Add a short classifier timeout and fail-open to `others:Low` for complex/freeform requests, then run memory extraction asynchronously so Stage 1 latency is not tied to slow local LLM calls.

**Log evidence:**
```
2026-07-06 01:20:12 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-07-06 01:20:57 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-07-06 01:21:34 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI (claude) failed (exit 1): Failed to authenticate. API Error: 401 Invalid authentication credentials
```
```
2026-07-06 01:22:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (37446ms) params={}
```

---

## Issue 3 [LOW]

**Turn:** 2026-07-06 01:24:57
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers,

**Problem:** Classifier emitted another unsupported intent label before falling back to others.

**Root cause:** Stage 1 returned `web automation`, which is not a configured class. The fallback to `others:Low` correctly escalated the complex coding request, but the classifier is still producing labels outside the allowed protocol.

**Suggested fix:** Update the Stage 1 prompt/schema to reject non-enum labels, or map `web automation` to `others` without warning when the request is a coding/project task.

**Log evidence:**
```
2026-07-06 01:24:55 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-06 01:24:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1688ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-07-06 01:24:57
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers,

**Problem:** Stage 3 took over nine minutes to complete a coding request.

**Root cause:** The Stage 3 stream ran from 01:24:56 to 01:34:13. During that window, the auxiliary local LLM stack timed out twice and then failed Claude auth, and heartbeat warnings appeared. The request eventually finished but with degraded UX.

**Suggested fix:** Separate Stage 3 execution from memory extraction/fallback LLM work, enforce per-subtask timeouts, and surface progress heartbeats so long coding tasks do not appear stalled.

**Log evidence:**
```
2026-07-06 01:24:56 INFO [jane.proxy] [audit-178331] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-07-06 01:25:39 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-07-06 01:26:24 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-07-06 01:26:30 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI (claude) failed (exit 1): Failed to authenticate. API Error: 401 Invalid authentication credentials
```
```
2026-07-06 01:34:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (557104ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-06 01:34:45
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 execution was cancelled after the client disconnected or timed out.

**Root cause:** The self-heal request was routed to Stage 3 correctly, but after about 261 seconds the proxy logged client disconnect and cancelled the brain stream. No final result reached the user.

**Suggested fix:** For long-running self-heal/code tasks, run Stage 3 as a resumable background job with persistent task state and stream reconnection instead of cancelling brain execution on client disconnect.

**Log evidence:**
```
2026-07-06 01:34:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-07-06 01:39:06 INFO [jane.proxy] [audit-178331] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-06 01:39:06 WARNING [jane.proxy] [audit-178331] Brain execution cancelled (stream) after 260874ms — likely client disconnect or timeout. Stack:
```
```
2026-07-06 01:39:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (261230ms)
```

---

