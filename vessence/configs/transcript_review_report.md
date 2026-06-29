# Transcript Quality Review — 2026-06-28

Generated: 2026-06-29 01:38:00

## Issue 1 [LOW]

**Turn:** 2026-06-28 01:10:40
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed intent taxonomy, so the pipeline normalized it to others:Low. The final route to Stage 3 was acceptable, but the raw classifier output is not schema-compliant.

**Suggested fix:** In intent_classifier.v3.classifier, enforce a closed enum with retry or deterministic normalization for known aliases such as 'web automation'.

**Log evidence:**
```
2026-06-28 01:10:38 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-28 01:10:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1087ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-28 01:10:57
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an out-of-schema 'force stage3' label.

**Root cause:** The classifier attempted to output routing behavior as an intent class. The pipeline recovered by mapping it to others:Low, but this shows the classifier prompt/schema is not constraining outputs tightly enough.

**Suggested fix:** Tighten the classifier prompt and parser so routing hints like 'force stage3' are represented as metadata or simply mapped to the valid 'others' class without warning.

**Log evidence:**
```
2026-06-28 01:10:56 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-28 01:10:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1121ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-28 01:11:14
**User said:** use the source code as your guide

**Problem:** A contextual Stage 3 follow-up was sent without conversation history or file context.

**Root cause:** The same audit session had prior turns, but Stage 3 was invoked with history=0 and file_ctx=False. This made the standalone follow-up ambiguous to the brain.

**Suggested fix:** Preserve session history for Stage 3 calls keyed by sid/audit id, and attach source-code context or route to the Codex/code adapter when the user asks to use source code.

**Log evidence:**
```
2026-06-28 01:11:12 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-28 01:11:14 INFO [jane.proxy] [audit-178262] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-28 01:11:28
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 took about 3 minutes for a short request, with memory extraction failures during the request.

**Root cause:** The short-term memory extractor attempted unavailable or timing-out CLIs while the Stage 3 request was open: primary timed out, gemini failed, and claude was not installed.

**Suggested fix:** Run short-term memory extraction asynchronously after responding, validate configured CLI fallbacks at startup, and remove missing fallback commands such as claude from the runtime path.

**Log evidence:**
```
2026-06-28 01:11:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-28 01:12:07 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-28 01:12:53 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-28 01:14:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (180644ms)
```

---

## Issue 5 [LOW]

**Turn:** 2026-06-28 01:14:33
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 again emitted an out-of-schema 'web automation' label.

**Root cause:** The classifier treated a web/code task as a new class instead of returning a valid taxonomy value. The fallback to others preserved routing, but classifier output remained invalid.

**Suggested fix:** Add explicit classifier examples for code/web-project requests and force valid enum output before accepting the model response.

**Log evidence:**
```
2026-06-28 01:14:31 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-28 01:14:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1040ms) params={}
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-28 01:14:33
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 response latency was extremely high for an interactive assistant turn.

**Root cause:** The Stage 3 request stayed open for 535234ms. During the request, the memory extractor also hit failed CLI fallbacks, adding avoidable delay and noise.

**Suggested fix:** Move large coding tasks to a background job/progress model, keep the streaming response alive with heartbeats, and make memory extraction non-blocking.

**Log evidence:**
```
2026-06-28 01:14:32 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-28 01:15:14 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-28 01:15:38 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```
```
2026-06-28 01:23:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (535234ms)
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-06-28 01:23:33
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 was canceled before completing the self-heal task.

**Root cause:** The brain ran for over 6 minutes, the client disconnected, and jane.proxy canceled the brain execution after 395953ms. The user-facing task did not complete through the pipeline.

**Suggested fix:** For android_crash_report/self-heal tasks, detach execution from the client stream into a resumable background job and do not cancel the brain solely because the client disconnects.

**Log evidence:**
```
2026-06-28 01:23:31 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-06-28 01:30:09 INFO [jane.proxy] [audit-178262] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-28 01:30:09 WARNING [jane.proxy] [audit-178262] Brain execution cancelled (stream) after 395953ms — likely client disconnect or timeout. Stack:
```
```
2026-06-28 01:30:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (398328ms)
```

---

