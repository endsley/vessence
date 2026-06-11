# Transcript Quality Review — 2026-06-10

Generated: 2026-06-11 01:35:18

## Issue 1 [LOW]

**Turn:** 2026-06-10 01:14:01
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned free-form class 'web automation' instead of one of the supported enum values. The fallback to others correctly escalated to Stage 3, so this was not user-breaking.

**Suggested fix:** Constrain the classifier output to the allowed intent enum with strict parsing, or add a supported code/project-work intent that intentionally routes to Stage 3.

**Log evidence:**
```
2026-06-10 01:14:00 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-10 01:14:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (772ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-10 01:14:15
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported 'force stage3' label.

**Root cause:** The classifier recognized the turn should escalate, but produced an out-of-schema label. The pipeline recovered by mapping it to others.

**Suggested fix:** Teach the classifier that escalation is represented by the supported 'others' intent plus low confidence, not by inventing a 'force stage3' class.

**Log evidence:**
```
2026-06-10 01:14:14 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-10 01:14:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1266ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-10 01:15:16
**User said:** use the source code as your guide

**Problem:** Context-dependent follow-up was sent to Stage 3 with no conversation history.

**Root cause:** The same audit session had prior turns, but jane.proxy logged history=0 for the Stage 3 call. This turn depends on the previous question, so Stage 3 may not know what source-code question the user is referring to.

**Suggested fix:** Persist and pass session history into Stage 3 calls, or have Stage 3 set a pending_action when asking for source-code confirmation so pending_action_resolver routes the next reply without reclassification.

**Log evidence:**
```
2026-06-10 01:14:15 INFO [jane.proxy] [audit-178106] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-10 01:15:16 INFO [jane.proxy] [audit-178106] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-10 01:15:31
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 latency was very high for a short project-familiarization request.

**Root cause:** The Stage 3 end-to-end duration was 203105ms, with no intermediate progress or handler handoff shown in the logs.

**Suggested fix:** Run long codebase exploration as an async job with progress updates, or stream Stage 3 tool/activity status so the user is not left waiting silently.

**Log evidence:**
```
2026-06-10 01:15:31 INFO [jane.proxy] [audit-178106] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-10 01:18:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (203105ms)
```

---

## Issue 5 [LOW]

**Turn:** 2026-06-10 01:18:59
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 again emitted unsupported 'web automation' before falling back.

**Root cause:** The classifier taxonomy does not include the label the model wants to use for code/web-app work, so it logs a warning and coerces to others.

**Suggested fix:** Either add a supported project/web-app-work intent that routes to Stage 3, or enforce enum-only classifier decoding.

**Log evidence:**
```
2026-06-10 01:18:56 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-10 01:18:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1022ms) params={}
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-10 01:18:59
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 took nearly 11 minutes to finish the turn.

**Root cause:** The complex site-wide implementation request was handled synchronously by Stage 3 and did not complete until 651831ms later. The logs also show LLM fallback timeouts during the same window.

**Suggested fix:** Move long-running implementation work to a cancellable background task with progress events; shorten or isolate auxiliary LLM timeouts so memory extraction cannot compete with the main response path.

**Log evidence:**
```
2026-06-10 01:18:57 INFO [jane.proxy] [audit-178106] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-10 01:19:39 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-10 01:20:24 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-10 01:29:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (651831ms)
```

---

## Issue 7 [LOW]

**Turn:** 2026-06-10 01:18:59
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Short-term memory extraction failed after the long Stage 3 turn.

**Root cause:** The memory extractor's primary and gemini fallback CLI calls timed out, then the claude fallback failed because the claude CLI was not installed.

**Suggested fix:** Configure only installed LLM backends for memory extraction, lower fallback timeouts, and run extraction fully out of band from the user-facing request path.

**Log evidence:**
```
2026-06-10 01:30:34 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-10 01:31:19 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-10 01:31:19 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-10 01:31:19 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```

---

