# Transcript Quality Review — 2026-06-13

Generated: 2026-06-14 01:32:59

## Issue 1 [LOW]

**Turn:** 2026-06-13 01:12:51
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed intent schema, so the pipeline coerced it to others:Low. Escalation was acceptable, but the classifier/schema contract is leaky.

**Suggested fix:** Constrain the Stage 1 model output to the canonical intent enum, or map 'web automation' explicitly to the intended supported class before logging it as unknown.

**Log evidence:**
```
2026-06-13 01:12:48 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-13 01:12:48 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1126ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-13 01:13:29
**User said:** right now, you are using the same codex process for each prompt instead of spawning a new one each time right for the stage 3 brain?

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned 'force stage3', which is not in the allowed intent schema. The fallback to others:Low routed the request to Stage 3, but the unknown label indicates prompt/schema drift.

**Suggested fix:** Add strict enum validation at the classifier prompt/API layer and either remove non-canonical labels like 'force stage3' from examples or map them internally without warning.

**Log evidence:**
```
2026-06-13 01:13:26 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-13 01:13:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (8078ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-13 01:15:15
**User said:** use the source code as your guide

**Problem:** Stage 3 received no conversation history for a context-dependent follow-up.

**Root cause:** The stream_message call used the same audit session id but logged history=0, so the frontier brain could not see the previous Waterlily/Codex context for a pronoun-style follow-up.

**Suggested fix:** Fix Stage 3 session history plumbing so sid_override sessions load prior turns before calling stream_message; add a regression test where a short follow-up depends on the previous user turn.

**Log evidence:**
```
2026-06-13 01:15:15 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-13 01:15:15 INFO [jane.proxy] [audit-178132] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-13 01:15:36
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 turn took about 230 seconds.

**Root cause:** The Stage 3 path completed only after multiple 45-second CLI LLM timeouts in the short-term memory extractor/fallback chain, producing very high latency for the user.

**Suggested fix:** Move short-term memory extraction off the blocking response path or enforce a much smaller timeout with best-effort failure; avoid sequential primary/gemini/claude retries during an active user response.

**Log evidence:**
```
2026-06-13 01:15:50 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-13 01:16:35 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-13 01:17:20 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-13 01:17:20 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-13 01:19:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (230283ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-13 01:15:36
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 again received no prior conversation history for a follow-up request.

**Root cause:** Despite the same audit session id, stream_message logged history=0. The request depends on earlier turns establishing Waterlily context, but Stage 3 was invoked without that history.

**Suggested fix:** Persist and reload conversation turns for the Stage 3 brain under the audit/session id; verify sid_override=True does not accidentally start a fresh empty history.

**Log evidence:**
```
2026-06-13 01:15:35 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-13 01:15:36 INFO [jane.proxy] [audit-178132] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-13 01:19:38
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers, I would like you to go over the entire site and when detected

**Problem:** Stage 3 turn took about 680 seconds.

**Root cause:** The Stage 3 path hit sequential CLI LLM timeout fallbacks and did not finish for more than 11 minutes. This is user-facing latency even though the initial Stage 1 escalation was appropriate.

**Suggested fix:** Remove blocking fallback LLM calls from the live Stage 3 request path, cap total auxiliary-task latency, and stream a progress/status response if long-running code work is intentionally continuing.

**Log evidence:**
```
2026-06-13 01:20:11 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-13 01:20:56 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-13 01:30:57 INFO [jane.proxy] [audit-178132] Jane stream pipeline task finished
```
```
2026-06-13 01:30:57 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (679575ms)
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-06-13 01:19:38
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers, I would like you to go over the entire site and when detected

**Problem:** Stage 3 had no previous Waterlily project context despite a multi-turn setup.

**Root cause:** The final implementation request was sent to stream_message with history=0 and file_ctx=False, so Stage 3 could not use the earlier 'source code as your guide' and 'familiarize yourself' turns unless it independently rediscovered everything.

**Suggested fix:** Ensure Stage 3 loads both chat history and any established file/project context for the same session before handling complex follow-up work.

**Log evidence:**
```
2026-06-13 01:19:37 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-13 01:19:37 INFO [jane.proxy] [audit-178132] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```

---

