# Transcript Quality Review — 2026-06-15

Generated: 2026-06-16 01:33:10

## Issue 1 [LOW]

**Turn:** 2026-06-15 01:13:51
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 produced an unsupported class before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed taxonomy, so the pipeline coerced it to others:Low. Routing to Stage 3 was acceptable, but the classifier contract is not enforced.

**Suggested fix:** Constrain classifier output to a strict enum or add an explicit alias map/test for unsupported labels like 'web automation'.

**Log evidence:**
```
2026-06-15 01:13:49 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-15 01:13:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (909ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-15 01:14:09
**User said:** right now, you are using the same codex process for each prompt instead of spawning a

**Problem:** Stage 3 response was very slow for an architecture/status question.

**Root cause:** The turn escalated to Stage 3 and took 121146ms end to end. A broadcast summary subprocess also timed out during the same request, showing auxiliary LLM work was unhealthy while the foreground request was running.

**Suggested fix:** Answer runtime architecture questions from deterministic config/source inspection when possible, and decouple broadcast summaries from foreground Stage 3 latency with a circuit breaker/backoff.

**Log evidence:**
```
2026-06-15 01:14:08 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```
```
2026-06-15 01:15:08 WARNING [jane.broadcast] Broadcast summary failed: Command '['claude', '--model', 'haiku', '--print']' timed out after 50 seconds
```
```
2026-06-15 01:16:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (121146ms)
```

---

## Issue 3 [LOW]

**Turn:** 2026-06-15 01:14:09
**User said:** right now, you are using the same codex process for each prompt instead of spawning a

**Problem:** Stage 1 produced another unsupported class.

**Root cause:** The classifier returned 'force stage3', which is a routing intent rather than a valid category, and the pipeline coerced it to others.

**Suggested fix:** Keep routing directives separate from intent labels, or add a validated 'escalate' field instead of letting the classifier emit pseudo-classes.

**Log evidence:**
```
2026-06-15 01:14:07 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-15 01:14:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1036ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-15 01:16:25
**User said:** use the source code as your guide

**Problem:** Context-dependent follow-up reached Stage 3 with no logged conversation or file context.

**Root cause:** The user reply depended on the prior turn, but the Stage 3 call logged history=0 and file_ctx=False, with no pending_action_resolver entry. The only recorded prompt context was the 33-character follow-up.

**Suggested fix:** Carry session transcript/source context into Stage 3 calls, or maintain a durable per-session brain keyed by sid and log that context path explicitly.

**Log evidence:**
```
2026-06-15 01:16:25 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-15 01:16:25 INFO [jane.proxy] [audit-178150] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-15 01:16:48
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 foreground flow was degraded by repeated auxiliary LLM timeouts.

**Root cause:** The request took 220937ms. During it, the primary LLM, Gemini fallback, Claude fallback, short-term extractor, and broadcast summary all timed out.

**Suggested fix:** Move memory extraction and broadcast summaries off the foreground path, add timeout backoff/circuit breaking, and use bounded local source indexing for project familiarization.

**Log evidence:**
```
2026-06-15 01:16:55 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-15 01:17:40 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-15 01:18:25 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-15 01:18:25 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-15 01:20:28 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (220937ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-15 01:20:37
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Long project implementation request never completed for the user.

**Root cause:** Stage 3 ran for more than 12 minutes, the client disconnected, and the brain execution was cancelled after 760215ms. The Stage 3 call also logged history=0 and file_ctx=False for a source-code-heavy request.

**Suggested fix:** Route long code/project work to a durable background Codex job with progress events and source access; do not cancel the job solely because the streaming client disconnects.

**Log evidence:**
```
2026-06-15 01:20:35 INFO [jane.proxy] [audit-178150] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-15 01:33:17 INFO [jane.proxy] [audit-178150] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-15 01:33:18 WARNING [jane.proxy] [audit-178150] Brain execution cancelled (stream) after 760215ms — likely client disconnect or timeout. Stack:
```
```
2026-06-15 01:33:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (762379ms)
```

---

## Issue 7 [LOW]

**Turn:** 2026-06-15 01:20:37
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 again emitted unsupported 'web automation' for a code/project request.

**Root cause:** The classifier generated a non-taxonomy label and the pipeline collapsed it to others:Low, losing the distinction that this was a long-running project/code task.

**Suggested fix:** Add a valid project/code-work intent that routes to a background implementation path, or normalize 'web automation' to that intent instead of generic others.

**Log evidence:**
```
2026-06-15 01:20:34 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-15 01:20:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1081ms) params={}
```

---

