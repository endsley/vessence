# Transcript Quality Review — 2026-06-26

Generated: 2026-06-27 01:30:51

## Issue 1 [LOW]

**Turn:** 2026-06-26 01:13:43
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others

**Root cause:** The classifier returned 'web automation', which is not in the v3 intent ontology, so the pipeline coerced it to others:Low. Routing still escalated to Stage 3, so this was not user-facing breakage.

**Suggested fix:** Constrain classifier outputs to the allowed enum at decode/prompt level, or add a supported project/web_work intent that deliberately escalates to Stage 3.

**Log evidence:**
```
2026-06-26 01:13:41 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-26 01:13:41 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (905ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-26 01:14:02
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others

**Root cause:** The classifier returned 'force stage3', which is not in the allowed intent set. The fallback to others still routed correctly to Stage 3.

**Suggested fix:** Teach the classifier that meta/system questions should classify as others, or add a valid force_stage3 internal route instead of allowing free-form labels.

**Log evidence:**
```
2026-06-26 01:13:59 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-26 01:14:00 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-26 01:14:02
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 3 response latency was excessive for a short meta question

**Root cause:** The turn took about 200 seconds end-to-end in Stage 3 despite a 132-character prompt. No Stage 2 handler was involved.

**Suggested fix:** Add a lightweight deterministic handler for runtime/meta-status questions, or enforce a shorter Stage 3 timeout with a partial/status response for voice and chat clients.

**Log evidence:**
```
2026-06-26 01:14:01 INFO [jane.proxy] [audit-178245] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-26 01:17:20 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (200068ms)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-26 01:17:34
**User said:** use the source code as your guide

**Problem:** Stage 3 response latency was high for a short follow-up

**Root cause:** The turn escalated to Stage 3 and took about 41 seconds for a 33-character prompt. Immediately afterward, the CLI LLM stack reported timeout/fallback problems.

**Suggested fix:** Keep the persistent Stage 3 process warm and add health checks around the CLI LLM adapter so slow or wedged calls fail fast before blocking the user turn.

**Log evidence:**
```
2026-06-26 01:17:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-26 01:18:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (41301ms)
```
```
2026-06-26 01:18:10 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-26 01:18:16
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 was severely delayed by failing LLM fallback calls

**Root cause:** The request escalated to Stage 3, then the primary, gemini fallback, and claude fallback CLI calls each timed out after 45 seconds. The full turn took about 236 seconds.

**Suggested fix:** Put hard per-turn deadlines around Stage 3 and memory extraction, skip nonessential memory extraction when the main response is already slow, and mark failed CLI backends unhealthy before retrying them on the same turn.

**Log evidence:**
```
2026-06-26 01:18:15 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-26 01:18:56 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-26 01:19:41 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-26 01:22:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (236060ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-26 01:18:16
**User said:** please familiarize yourself with the waterlily project

**Problem:** Short-term memory extraction failed after the turn

**Root cause:** The short_term_extractor used the same unhealthy CLI LLM path and timed out after the primary and fallback attempts failed.

**Suggested fix:** Decouple memory extraction from the user response path and queue it asynchronously with retry/backoff; do not run it through an already-failing CLI backend during the active turn.

**Log evidence:**
```
2026-06-26 01:19:41 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```

---

## Issue 7 [LOW]

**Turn:** 2026-06-26 01:22:20
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others

**Root cause:** The classifier returned 'web automation', which is outside the allowed class set. The fallback still escalated to Stage 3, which was the correct broad route for a complex coding request.

**Suggested fix:** Add an explicit coding/project_work or web_automation intent that maps to Stage 3, or tighten the classifier prompt/schema so unsupported labels cannot be returned.

**Log evidence:**
```
2026-06-26 01:22:14 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-26 01:22:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1079ms) params={}
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-06-26 01:22:20
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to complete before client disconnect/timeout

**Root cause:** The brain worked for nearly 10 minutes, the client disconnected at 01:32:09, and the stream was cancelled after 589064ms. This is user-facing failure for a complex implementation request.

**Suggested fix:** For long coding tasks, immediately acknowledge and switch to an asynchronous job/progress model; stream periodic heartbeat/status chunks and avoid holding the Android/client request open for the whole implementation.

**Log evidence:**
```
2026-06-26 01:22:15 INFO [jane.proxy] [audit-178245] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-26 01:32:09 INFO [jane.proxy] [audit-178245] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-26 01:32:09 WARNING [jane.proxy] [audit-178245] Brain execution cancelled (stream) after 589064ms — likely client disconnect or timeout. Stack:
```
```
2026-06-26 01:32:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (595135ms)
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-06-26 01:22:20
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 infrastructure became unhealthy after long-running/cancelled work

**Root cause:** After the cancelled long Stage 3 turn, heartbeat pings failed and Standing Brain startup later failed because Codex's sqlite state database under /home/chieh/.codex was locked.

**Suggested fix:** Ensure cancelled Stage 3/Codex processes are reaped cleanly and release sqlite handles; add single-writer locking or per-session Codex state directories so concurrent standing-brain startup cannot collide on /home/chieh/.codex.

**Log evidence:**
```
2026-06-26 01:37:21 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-06-26 01:37:38 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-06-26 01:43:17 ERROR [jane.web] Standing Brain startup failed: Codex app-server stdout closed. Error: failed to initialize sqlite state runtime under /home/chieh/.codex: failed to initialize state runtime at /home/chieh/.codex: error returned from database: (code: 5) database is locked
```

---

