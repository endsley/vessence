# Transcript Quality Review — 2026-06-24

Generated: 2026-06-25 01:29:46

## Issue 1 [LOW]

**Turn:** 2026-06-24 01:15:03
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 produced an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the supported intent taxonomy. The fallback to others preserved the correct Stage 3 route, but the classifier contract is not being enforced.

**Suggested fix:** Constrain Stage 1 decoding to the allowed intent enum, or retry once when the model returns an unknown label before coercing to others.

**Log evidence:**
```
2026-06-24 01:15:01 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-24 01:15:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1199ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-24 01:15:33
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 produced an out-of-schema intent label and took over 6 seconds before fallback.

**Root cause:** The classifier returned 'force stage3', which is not a valid class, then fell back to others. The Stage 1 pass alone took 6228ms.

**Suggested fix:** Add strict enum validation for classifier output and a fast rule-based Stage 3 route for architecture/source-code questions.

**Log evidence:**
```
2026-06-24 01:15:27 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-24 01:15:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (6228ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-24 01:15:52
**User said:** use the source code as your guide

**Problem:** Stage 3 follow-up context was dropped for a context-dependent reply.

**Root cause:** The user reply depended on the previous turn, but the Stage 3 proxy logged history=0 for the same session. No pending_action resolver applied, so Stage 3 received only the short follow-up without its antecedent.

**Suggested fix:** Load prior turns by session id before Stage 3 escalation, or create a Stage 3 follow-up context record so short replies like this include the previous request.

**Log evidence:**
```
2026-06-24 01:15:33 INFO [jane.proxy] [audit-178227] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-24 01:15:52 INFO [jane.proxy] [audit-178227] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-24 01:16:12
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 kept the turn open for over 3 minutes.

**Root cause:** The request escalated to Stage 3 and did not finish until 186155ms later. No Stage 2 handler or progress/async handoff is shown.

**Suggested fix:** For repo-familiarization tasks, return a quick acknowledgement and run the project scan asynchronously with progress events instead of blocking the conversation turn.

**Log evidence:**
```
2026-06-24 01:16:08 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-24 01:19:14 INFO [jane.proxy] [audit-178227] Jane stream pipeline task finished
```
```
2026-06-24 01:19:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (186155ms)
```

---

## Issue 5 [LOW]

**Turn:** 2026-06-24 01:19:22
**User said:** currently, the waterlily site is web only meant for browsers on laptops and

**Problem:** Stage 1 again produced an out-of-schema intent label before fallback.

**Root cause:** The classifier returned 'web automation', which the pipeline does not accept, then coerced it to others.

**Suggested fix:** Update the classifier prompt/schema so development and web-automation requests map directly to the intended Stage 3 class without invalid intermediate labels.

**Log evidence:**
```
2026-06-24 01:19:18 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-24 01:19:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2219ms) params={}
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-24 01:19:22
**User said:** currently, the waterlily site is web only meant for browsers on laptops and

**Problem:** Stage 3 took almost 12 minutes and logged repeated LLM timeout failures.

**Root cause:** The Stage 3 run lasted 712002ms. During that window, the LLM CLI path failed through primary, gemini fallback, and claude fallback, and short-term memory extraction also timed out.

**Suggested fix:** Move memory extraction off the response hot path, cap serial fallback time, and enforce a hard Stage 3 request budget with a streamed progress or background-task handoff for long codebase work.

**Log evidence:**
```
2026-06-24 01:19:22 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-24 01:20:00 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-24 01:20:46 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-24 01:21:31 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-24 01:21:31 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-24 01:31:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (712002ms)
```

---

