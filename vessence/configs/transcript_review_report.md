# Transcript Quality Review — 2026-06-29

Generated: 2026-06-30 01:38:38

## Issue 1 [LOW]

**Turn:** 2026-06-29 01:16:31
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an out-of-schema 'force stage3' intent before falling back to others.

**Root cause:** The v3 qwen classifier returned routing behavior as the class name. The runtime registry rejected it and normalized the turn to others:Low, so routing recovered but the classifier output was not schema-compliant.

**Suggested fix:** Constrain intent_classifier.v3.classifier to a closed enum with retry on invalid classes, or normalize routing hints like 'force stage3' to the valid 'others' class before logging a warning.

**Log evidence:**
```
2026-06-29 01:16:29 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-29 01:16:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1183ms) params={}
```
```
2026-06-29 01:16:30 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-06-29 01:18:11
**User said:** use the source code as your guide

**Problem:** Context-dependent follow-up was sent to Stage 3 as a standalone prompt with no history or file context.

**Root cause:** The turn was reclassified through Stage 1 instead of being resolved as contextual continuation, and the Stage 3 proxy shows history=0 and file_ctx=False. The brain therefore received only the 33-character follow-up, not the prior architecture question or source context.

**Suggested fix:** Preserve and pass session history into Stage 3 for audit sessions, and route source-code follow-ups to the code/Codex adapter or attach repository context when the user asks to use source code.

**Log evidence:**
```
2026-06-29 01:18:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1183ms) params={}
```
```
2026-06-29 01:18:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-29 01:18:11 INFO [jane.proxy] [audit-178271] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-29 01:18:24
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 latency was excessive for a short project-familiarization request.

**Root cause:** During the open Stage 3 request, the short-term memory extractor tried a primary CLI that timed out, then a gemini fallback that timed out, then a missing claude fallback. The pipeline did not finish until 149480ms.

**Suggested fix:** Run short-term memory extraction asynchronously after responding, validate configured CLI fallbacks at startup, and remove or disable missing fallback commands such as claude.

**Log evidence:**
```
2026-06-29 01:18:23 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-29 01:18:52 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-29 01:19:37 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-29 01:19:37 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-29 01:20:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (149480ms)
```

---

## Issue 4 [LOW]

**Turn:** 2026-06-29 01:21:00
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 emitted an out-of-schema 'web automation' class for a web/code task.

**Root cause:** The classifier generated a class not present in the runtime handler registry. The pipeline recovered by mapping it to others:Low and escalating, but the raw classifier output violated the intent schema.

**Suggested fix:** Add explicit classifier examples for web/code-project requests and enforce valid enum output, or add a real supported web_automation class if that is intended to be a first-class route.

**Log evidence:**
```
2026-06-29 01:20:56 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-29 01:20:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2041ms) params={}
```
```
2026-06-29 01:20:57 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-29 01:21:00
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Large coding request held the interactive Stage 3 stream open for over 13 minutes.

**Root cause:** The coding task ran synchronously through Stage 3 until the pipeline ended at 797507ms. Memory extraction also hit repeated CLI fallback failures during the request, adding avoidable delay and noise.

**Suggested fix:** Detect large coding/audit tasks and move them to a resumable background job with progress events and heartbeats; make memory extraction non-blocking.

**Log evidence:**
```
2026-06-29 01:20:59 INFO [jane.proxy] [audit-178271] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-29 01:21:39 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-29 01:22:24 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```
```
2026-06-29 01:34:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (797507ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-29 01:34:21
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 was cancelled before completing the android_crash_report self-heal task.

**Root cause:** The client disconnected while the brain was still working. The proxy logged that it would wait for the adapter task, but the brain execution was cancelled about two seconds later, so the self-heal task did not complete through the pipeline.

**Suggested fix:** For android_crash_report/self-heal tasks, detach execution from the client stream into a resumable background job, keep heartbeats alive, and do not cancel the brain solely because the client disconnects.

**Log evidence:**
```
2026-06-29 01:34:21 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-06-29 01:35:33 INFO [jane.proxy] [audit-178271] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-29 01:35:35 WARNING [jane.proxy] [audit-178271] Brain execution cancelled (stream) after 71869ms — likely client disconnect or timeout. Stack:
```
```
2026-06-29 01:35:35 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (74908ms)
```

---

