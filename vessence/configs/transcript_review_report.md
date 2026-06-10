# Transcript Quality Review — 2026-06-09

Generated: 2026-06-10 01:30:45

## Issue 1 [LOW]

**Turn:** 2026-06-09 01:18:50
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before coercing to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed class set, so the pipeline downgraded it to others:Low and escalated to Stage 3.

**Suggested fix:** Constrain the classifier prompt/output parser to the exact enum, or map 'web automation' and similar project/code requests explicitly to others without warning.

**Log evidence:**
```
2026-06-09 01:18:49 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-09 01:18:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (780ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-09 01:19:05
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 3 did not receive conversation history for a follow-up question.

**Root cause:** Every OpenAI stream for the same session id shows history=0, so the brain could not rely on previous turns when answering a contextual continuation.

**Suggested fix:** Fix session history lookup/persistence for sid_override sessions so stream_message receives prior turns for the same conversation id.

**Log evidence:**
```
2026-06-09 01:18:50 INFO [jane.proxy] [audit-178098] stream_message brain=OpenAI history=0 msg_len=56 file_ctx=False
```
```
2026-06-09 01:19:05 INFO [jane.proxy] [audit-178098] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```

---

## Issue 3 [LOW]

**Turn:** 2026-06-09 01:19:05
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported intent label before coercing to others.

**Root cause:** The classifier returned 'force stage3', which is not in the allowed class set, so the pipeline downgraded it to others:Low and escalated.

**Suggested fix:** Update the classifier prompt/parser to reject non-enum labels, and normalize meta-routing labels like 'force stage3' to others internally.

**Log evidence:**
```
2026-06-09 01:19:04 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-09 01:19:04 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (695ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-09 01:20:59
**User said:** use the source code as your guide

**Problem:** Stage 3 did not receive prior conversation context for an explicitly contextual instruction.

**Root cause:** The OpenAI stream for the same audit session again shows history=0, so the brain likely received only 'use the source code as your guide' without the preceding project question.

**Suggested fix:** Ensure conversation history is appended before each Stage 3 call and retrieved by session id, including web/non-voice audit sessions.

**Log evidence:**
```
2026-06-09 01:20:58 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-09 01:20:59 INFO [jane.proxy] [audit-178098] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-09 01:21:16
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 ran for over three minutes on a broad project-familiarization request.

**Root cause:** The Stage 3 brain completed only after 193786ms, indicating the request was allowed to run synchronously for a long time instead of giving progress or using a background task flow.

**Suggested fix:** Add a timeout/progress strategy for long Stage 3 codebase exploration requests, with partial status updates and resumable background execution.

**Log evidence:**
```
2026-06-09 01:21:16 INFO [jane.proxy] [audit-178098] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-09 01:24:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (193786ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-09 01:24:32
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to complete a large implementation request after the client disconnected.

**Root cause:** The brain worked for about 825 seconds, the client disconnected, and the stream task was cancelled. The user-facing request likely never received a completed answer or implementation result.

**Suggested fix:** Route long code implementation requests to a durable background Codex job with status polling instead of a single streaming request, and set practical execution timeouts with progress events.

**Log evidence:**
```
2026-06-09 01:24:32 INFO [jane.proxy] [audit-178098] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-09 01:38:17 INFO [jane.proxy] [audit-178098] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-09 01:38:17 WARNING [jane.proxy] [audit-178098] Brain execution cancelled (stream) after 824995ms — likely client disconnect or timeout. Stack:
```
```
2026-06-09 01:38:17 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (825214ms)
```

---

## Issue 7 [LOW]

**Turn:** 2026-06-09 01:24:32
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 emitted an unsupported intent label before coercing to others.

**Root cause:** The classifier returned 'web automation', which is outside the configured intent enum. The fallback to others was functionally acceptable, but the classifier output contract was violated.

**Suggested fix:** Add an enum-constrained decoder or post-classification normalization table for unsupported labels produced by the local classifier.

**Log evidence:**
```
2026-06-09 01:24:31 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-09 01:24:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (772ms) params={}
```

---

## Issue 8 [LOW]

**Turn:** 2026-06-09 01:24:32
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Short-term memory extraction failed during the Stage 3 request.

**Root cause:** The primary LLM and Gemini fallback both timed out after 45 seconds, then the Claude fallback was unavailable on PATH, causing the memory extractor to fail.

**Suggested fix:** Make memory extraction non-blocking and configure only installed fallback providers; add a shorter extractor-specific timeout and suppress unavailable CLI fallbacks.

**Log evidence:**
```
2026-06-09 01:25:15 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-09 01:26:00 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-09 01:26:00 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-09 01:26:00 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```

---

