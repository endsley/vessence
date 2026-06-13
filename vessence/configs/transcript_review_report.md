# Transcript Quality Review — 2026-06-12

Generated: 2026-06-13 01:31:56

## Issue 1 [LOW]

**Turn:** 2026-06-12 01:17:12
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the configured intent taxonomy, so the pipeline coerced it to others:Low. The final route to Stage 3 was acceptable, but the taxonomy mismatch creates noisy and brittle classification behavior.

**Suggested fix:** Constrain classifier output to the allowed enum in the prompt and add a normalization/test case for project/web-automation questions to route directly to others without warning.

**Log evidence:**
```
2026-06-12 01:17:10 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-12 01:17:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1113ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-12 01:17:27
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 3 took 107 seconds to answer a short architecture question.

**Root cause:** The turn correctly escalated to Stage 3, but the brain stream ran from 01:17:24/01:17:26 until 01:19:11. No handler or client-side activity explains the delay; the slowdown is inside Stage 3 brain execution.

**Suggested fix:** Add Stage 3 latency instrumentation around Codex/OpenAI calls and enforce a user-facing progress/timeout policy for short prompts, with cancellation or fallback when the brain exceeds the expected latency budget.

**Log evidence:**
```
2026-06-12 01:17:24 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```
```
2026-06-12 01:17:26 INFO [jane.proxy] [audit-178124] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-12 01:19:11 INFO [jane.proxy] [audit-178124] Jane stream pipeline task finished
```
```
2026-06-12 01:19:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (107070ms)
```

---

## Issue 3 [LOW]

**Turn:** 2026-06-12 01:17:27
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted another unsupported intent label.

**Root cause:** The classifier returned 'force stage3', which is not a supported category, so the pipeline coerced it to others:Low. Routing still reached Stage 3, but the classifier is not reliably honoring the schema.

**Suggested fix:** Use strict structured decoding or post-validate against the intent enum, and update the classifier prompt so meta/system questions are classified as others rather than inventing 'force stage3'.

**Log evidence:**
```
2026-06-12 01:17:23 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-12 01:17:23 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (909ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-12 01:19:37
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 latency was very high for a short project-orientation request.

**Root cause:** The pipeline correctly escalated to Stage 3, but execution took 192 seconds end-to-end. The logs show the OpenAI brain stream started at 01:19:37 and did not finish until 01:22:49.

**Suggested fix:** Add a bounded project-context gathering path for Stage 3, stream interim progress, and cap long repository scans with resumable summaries rather than blocking the whole response.

**Log evidence:**
```
2026-06-12 01:19:37 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-12 01:19:37 INFO [jane.proxy] [audit-178124] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-12 01:22:49 INFO [jane.proxy] [audit-178124] Jane stream pipeline task finished
```
```
2026-06-12 01:22:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (192044ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-12 01:22:56
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to complete a complex coding request before the client disconnected.

**Root cause:** The turn escalated correctly, but Stage 3 ran for about 13 minutes 50 seconds, hit repeated 45-second CLI timeouts in the memory extractor/fallback path, then the client disconnected and the brain execution was cancelled.

**Suggested fix:** For long coding tasks, acknowledge quickly, detach execution from the client stream, and provide resumable task status. Also disable or hard-timebox nonessential memory extraction on active Stage 3 coding turns so repeated CLI fallback timeouts cannot stall the request.

**Log evidence:**
```
2026-06-12 01:22:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-12 01:22:54 INFO [jane.proxy] [audit-178124] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-12 01:23:36 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-12 01:24:21 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-12 01:25:06 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-12 01:25:06 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-12 01:36:43 INFO [jane.proxy] [audit-178124] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-12 01:36:43 WARNING [jane.proxy] [audit-178124] Brain execution cancelled (stream) after 827633ms — likely client disconnect or timeout. Stack:
```
```
2026-06-12 01:36:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (830755ms)
```

---

## Issue 6 [LOW]

**Turn:** 2026-06-12 01:22:56
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 again produced an unsupported 'web automation' label.

**Root cause:** The classifier generated a non-enum intent for a coding/web-project request and the system fell back to others:Low. The fallback route was correct, but repeated unknown labels show the classifier contract is not enforced.

**Suggested fix:** Add schema-constrained classifier output and regression tests for web/project/coding requests so they classify as others or a deliberate coding/project intent.

**Log evidence:**
```
2026-06-12 01:22:52 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-12 01:22:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (923ms) params={}
```

---

