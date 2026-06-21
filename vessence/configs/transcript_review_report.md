# Transcript Quality Review — 2026-06-20

Generated: 2026-06-21 01:29:31

## Issue 1 [LOW]

**Turn:** 2026-06-20 01:20:48
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 classifier emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed class set, so the pipeline coerced it to others:Low. Routing to Stage 3 was acceptable, but the schema violation shows classifier drift.

**Suggested fix:** Constrain classifier output to the supported enum, and add explicit normalization/tests for project/source-code questions so they route cleanly to others without warnings.

**Log evidence:**
```
2026-06-20 01:20:47 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-20 01:20:47 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (3412ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-20 01:21:09
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 classifier emitted another unsupported intent label before fallback.

**Root cause:** The classifier returned 'force stage3', which is not a valid category. The fallback still escalated correctly, but classification output was not schema-compliant.

**Suggested fix:** Harden the classifier prompt/parser to only emit valid labels, and add a regression case for architecture/meta questions.

**Log evidence:**
```
2026-06-20 01:21:06 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-20 01:21:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2125ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-20 01:23:25
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 request completed with very high latency.

**Root cause:** After Stage 3 started, the short-term memory extractor made three sequential CLI LLM attempts, each timing out after 45 seconds. The request did not finish until 178339ms end-to-end.

**Suggested fix:** Move short_term_extractor off the user-facing request path, or enforce a short total timeout and run memory extraction asynchronously after streaming completes.

**Log evidence:**
```
2026-06-20 01:23:25 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-20 01:23:52 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-20 01:24:38 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-20 01:25:23 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-20 01:25:23 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-20 01:26:22 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (178339ms)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-06-20 01:26:29
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to deliver a response before the client disconnected.

**Root cause:** The complex implementation request was routed to Stage 3, but brain execution ran for over 12 minutes, the client disconnected, and the brain task was cancelled. The same short-term extractor CLI timeout pattern also occurred early in the request.

**Suggested fix:** For long coding tasks, acknowledge quickly and hand off to an asynchronous job with progress updates instead of holding the voice/chat stream open. Also decouple memory extraction from the live response path.

**Log evidence:**
```
2026-06-20 01:26:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-20 01:27:12 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-20 01:28:42 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-20 01:39:23 INFO [jane.proxy] [audit-178193] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-20 01:39:24 WARNING [jane.proxy] [audit-178193] Brain execution cancelled (stream) after 773372ms — likely client disconnect or timeout. Stack:
```
```
2026-06-20 01:39:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (777141ms)
```

---

