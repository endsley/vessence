# Transcript Quality Review — 2026-06-08

Generated: 2026-06-09 01:39:22

## Issue 1 [LOW]

**Turn:** 2026-06-08 01:14:40
**User said:** you have access to the water lily Wellness project right

**Problem:** Classifier produced an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not a supported category, so the pipeline coerced it to others:Low and escalated to Stage 3. Escalation was acceptable for this complex/project-context request, but the classifier contract is not being enforced.

**Suggested fix:** Constrain the Stage 1 classifier output to the allowed enum at decode/parse time, and add an explicit mapping or prompt examples for project/codebase-access questions to route directly to Stage 3 without warning.

**Log evidence:**
```
2026-06-08 01:14:38 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-08 01:14:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (864ms) params={}
```
```
2026-06-08 01:14:39 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=56 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-08 01:14:53
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 3 received no conversation history for a contextual follow-up question.

**Root cause:** The user asked a follow-up referencing the Stage 3 brain, but the proxy logged history=0, so Stage 3 was called without prior turns from the same audit session.

**Suggested fix:** Persist and pass recent conversation history for the sid/audit session into stream_message, or ensure sid_override resolves to the existing session history before Stage 3 invocation.

**Log evidence:**
```
2026-06-08 01:14:53 INFO [jane.proxy] [audit-178089] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-08 01:16:39 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (105558ms)
```

---

## Issue 3 [LOW]

**Turn:** 2026-06-08 01:14:53
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Classifier produced an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'force stage3', which is not a supported category. The fallback still escalated correctly, but the classifier is inventing routing labels outside the contract.

**Suggested fix:** Make the classifier parser reject or repair labels to the canonical enum, and update the classifier prompt so meta/system questions map to others or a supported Stage 3 escalation category.

**Log evidence:**
```
2026-06-08 01:14:52 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-08 01:14:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (811ms) params={}
```
```
2026-06-08 01:14:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-08 01:16:43
**User said:** use the source code as your guide

**Problem:** Stage 3 received no conversation history for an instruction that only makes sense as a follow-up.

**Root cause:** The user gave a contextual instruction after the previous turn, but Stage 3 was invoked with history=0, so the brain lacked the earlier question unless external state happened to preserve it elsewhere.

**Suggested fix:** Attach session history to Stage 3 calls for the same conversation id, especially when sid_override=True, and add a regression test for short follow-up commands after a long Stage 3 answer.

**Log evidence:**
```
2026-06-08 01:16:42 INFO [jane.proxy] [audit-178089] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```
```
2026-06-08 01:16:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (14584ms)
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-08 01:16:59
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3/memory side task hit repeated LLM CLI timeouts and missing fallback binary.

**Root cause:** After Stage 3 escalation, the short-term memory extractor tried a primary CLI, then Gemini, then Claude. Both primary and Gemini timed out after 45s, and Claude was not installed, producing a failed memory extraction.

**Suggested fix:** Separate memory extraction from the user-facing Stage 3 path, lower its timeout, and configure only available fallback providers or disable missing Claude fallback until installed.

**Log evidence:**
```
2026-06-08 01:17:24 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-08 01:18:09 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-08 01:18:09 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-08 01:18:09 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-08 01:16:59
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 response latency was extremely high for a simple project-familiarization request.

**Root cause:** The Stage 3 end-to-end time was 170163ms. Logs also show two 45s LLM timeout attempts in the same interval, indicating backend/fallback work contributed significant delay.

**Suggested fix:** Do not run slow auxiliary LLM fallback work inline with the response path; stream an immediate acknowledgement and run project indexing/familiarization as an asynchronous task with progress events.

**Log evidence:**
```
2026-06-08 01:16:59 INFO [jane.proxy] [audit-178089] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-08 01:17:24 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-08 01:18:09 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-08 01:19:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (170163ms)
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-06-08 01:19:52
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Long Stage 3 coding request was cancelled after the client disconnected, so the user likely did not receive a completed answer.

**Root cause:** Stage 3 ran for about 14 minutes, then the proxy logged client disconnect and brain execution cancellation after 840256ms.

**Suggested fix:** For long-running Stage 3/Codex tasks, detach execution from the HTTP/stream lifecycle, persist task state, and let the client reconnect or poll for completion instead of cancelling the brain on disconnect.

**Log evidence:**
```
2026-06-08 01:19:51 INFO [jane.proxy] [audit-178089] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-08 01:33:52 INFO [jane.proxy] [audit-178089] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-08 01:33:52 WARNING [jane.proxy] [audit-178089] Brain execution cancelled (stream) after 840256ms — likely client disconnect or timeout. Stack:
```
```
2026-06-08 01:33:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (840953ms)
```

---

## Issue 8 [LOW]

**Turn:** 2026-06-08 01:19:52
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Classifier produced an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is outside the supported intent set. The fallback to others did escalate to Stage 3, but the classifier continues to violate its schema.

**Suggested fix:** Add schema-constrained decoding or a strict enum validator with deterministic repair, and include examples for codebase/UI work so these requests classify to a supported Stage 3 route.

**Log evidence:**
```
2026-06-08 01:19:51 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-08 01:19:51 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (805ms) params={}
```
```
2026-06-08 01:19:51 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-06-08 01:19:52
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3/memory side task again hit repeated LLM CLI timeouts and missing fallback binary.

**Root cause:** The same primary/Gemini 45s timeouts and missing Claude CLI occurred during the long Stage 3 request, causing short-term memory extraction failure.

**Suggested fix:** Remove unavailable Claude from the fallback chain, add health checks for configured CLI providers at startup, and make memory extraction best-effort background work that cannot extend or destabilize Stage 3 turns.

**Log evidence:**
```
2026-06-08 01:20:35 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-08 01:21:20 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-08 01:21:20 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI not found: claude...
```
```
2026-06-08 01:21:20 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI not found: claude
```

---

