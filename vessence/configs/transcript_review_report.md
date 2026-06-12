# Transcript Quality Review — 2026-06-11

Generated: 2026-06-12 01:38:10

## Issue 1 [LOW]

**Turn:** 2026-06-11 01:13:56
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported class before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed class enum. The fallback route to Stage 3 was acceptable for this request, but the classifier contract is loose and creates noisy/fragile routing.

**Suggested fix:** Constrain classifier decoding to the known enum or add explicit normalization/tests for unsupported labels like 'web automation'.

**Log evidence:**
```
2026-06-11 01:13:55 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-11 01:13:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (854ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-11 01:14:09
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported meta-routing class.

**Root cause:** The classifier returned 'force stage3', which is not a valid category. The pipeline coerced it to others and escalated, but the classifier is leaking internal routing concepts as labels.

**Suggested fix:** Update the classifier prompt/schema so meta intents still produce a valid category, or validate with structured enum decoding before accepting model output.

**Log evidence:**
```
2026-06-11 01:14:08 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-11 01:14:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (662ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-11 01:16:01
**User said:** use the source code as your guide

**Problem:** Context-dependent follow-up was sent to Stage 3 with no logged conversation history or file context.

**Root cause:** The user reply depends on the previous turn, but the Stage 3 proxy call logged history=0 and file_ctx=False. If the frontier brain is not independently maintaining the same session, this turn is processed as an isolated vague instruction.

**Suggested fix:** Pass prior conversation history or a stable Stage 3 session context for same-sid turns, and add a regression test for short follow-ups like 'use the source code as your guide'.

**Log evidence:**
```
2026-06-11 01:16:00 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-11 01:16:01 INFO [jane.proxy] [audit-178115] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-11 01:16:14
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 took nearly three minutes for a project-familiarization request.

**Root cause:** The request escalated to Stage 3 and completed after 167372ms. There is no evidence of a fast acknowledgement, async job handoff, or progress update in the pipeline logs.

**Suggested fix:** Route long project-analysis tasks to an async job mode with immediate acknowledgement and progress streaming, instead of holding the voice/web pipeline synchronously.

**Log evidence:**
```
2026-06-11 01:16:14 INFO [jane.proxy] [audit-178115] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-11 01:19:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (167372ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-11 01:19:05
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 blocked the pipeline for over fourteen minutes on a complex coding request.

**Root cause:** The turn escalated synchronously to Stage 3 and finished after 847710ms. During the same window, the LLM-backed short-term extractor exhausted primary and fallback CLI calls with 45s timeouts, adding backend instability/noise around the long-running turn.

**Suggested fix:** Detect large coding/project tasks and convert them to async Codex work with an immediate user-facing acknowledgement. Put strict non-blocking timeouts around memory extraction/fallback LLM calls so they cannot degrade the active response path.

**Log evidence:**
```
2026-06-11 01:19:04 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-11 01:19:48 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-11 01:20:33 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-11 01:21:18 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-11 01:21:18 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-11 01:33:12 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (847710ms)
```

---

