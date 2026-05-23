# Transcript Quality Review — 2026-05-22

Generated: 2026-05-23 01:24:37

## Issue 1 [CRITICAL]

**Turn:** 2026-05-22 01:18:22
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** User request took ~2m32s to resolve, making the interaction unusable for real-time use.

**Root cause:** Stage 1 and escalation happened quickly, but Stage 3 did not complete for 152,337ms. Logs show no stage2 handler path or client-side recovery during this delay, indicating the slowdown is in Stage 3 execution rather than intent routing.

**Suggested fix:** Add per-stage timing instrumentation inside Stage 3 (LLM call vs tool call vs postprocessing), enforce a hard timeout with graceful partial-response fallback, and retry/failover policy for stalled frontier-brain responses.

**Log evidence:**
```
2026-05-22 01:18:21 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2166ms) params={}
```
```
2026-05-22 01:18:22 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=68 sid_override=True class_protocol=n/a
```
```
2026-05-22 01:20:22 INFO [jane.proxy] [audit-177942] Jane stream pipeline task finished
```
```
2026-05-22 01:20:22 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (152337ms)
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-22 01:20:39
**User said:** can you tell me if currently you are using cold decks or Claude cold as the base stage 3 brain

**Problem:** Turn took ~88s before completion despite no explicit tool invocation in the logs.

**Root cause:** Another long Stage 3 path with no Stage 2 fallback. Classifier escalated with low-confidence "others" and class protocol was unavailable, so the deterministic path was not used and the response depended on the slow Stage 3 route.

**Suggested fix:** Introduce a deterministic "system_identity/model_query" handler for this common class of questions or cache static answers, and set a shorter Stage 3 SLA budget for simple factual prompts.

**Log evidence:**
```
2026-05-22 01:20:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (936ms) params={}
```
```
2026-05-22 01:20:39 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-22 01:20:39 INFO [jane.proxy] [audit-177942] stream_message brain=OpenAI history=0 msg_len=94 file_ctx=False
```
```
2026-05-22 01:22:07 INFO [jane.proxy] [audit-177942] Jane stream pipeline task finished
```
```
2026-05-22 01:22:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (88061ms)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-22 01:22:20
**User said:** currently which large language model is being used as Jane Webb

**Problem:** Classifier emitted an unsupported class (`force stage3`) and fell back to `others`, reducing routing fidelity.

**Root cause:** Stage 1 logging shows the intent model returned a non-enumerated label (`qwen returned unknown class 'force stage3'`), and the pipeline normalized it to `others` with `class_protocol=n/a`, which can mask explicit routing intent and contributes to unnecessary Stage 3 ambiguity.

**Suggested fix:** Version and harden the Stage 1 class schema: add canonical mappings/aliases for `force stage3` (and similar control-intent tokens), and fail closed with explicit telemetry when unseen labels are returned instead of silently coercing to `others`.

**Log evidence:**
```
2026-05-22 01:22:19 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-22 01:22:19 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (685ms) params={}
```
```
2026-05-22 01:22:20 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=63 sid_override=True class_protocol=n/a
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-05-22 01:22:20
**User said:** currently which large language model is being used as Jane Webb

**Problem:** High end-to-end latency again (~74.6s) on an intent-only query.

**Root cause:** After Stage 1 fallback and Stage 3 escalation, completion came 74,638ms later. No Stage 2 fast-path or resolver bypass was used for this turn.

**Suggested fix:** As above for Stage 3 SLA: split Stage 3 latency budgets by query type and route static/meta-model questions to a cheap deterministic response path.

**Log evidence:**
```
2026-05-22 01:22:20 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=63 sid_override=True class_protocol=n/a
```
```
2026-05-22 01:22:20 INFO [jane.proxy] [audit-177942] stream_message brain=OpenAI history=0 msg_len=63 file_ctx=False
```
```
2026-05-22 01:23:34 INFO [jane.proxy] [audit-177942] Jane stream pipeline task finished
```
```
2026-05-22 01:23:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (74638ms)
```

---

