# Transcript Quality Review — 2026-06-21

Generated: 2026-06-22 01:29:25

## Issue 1 [LOW]

**Turn:** 2026-06-21 01:09:26
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed class set, so the v3 classifier normalized it to others:Low. The final Stage 3 routing was acceptable, but the classifier contract is not enforced.

**Suggested fix:** Constrain intent_classifier.v3.classifier to a fixed enum with structured decoding, or add an alias map for model-only labels like 'web automation'.

**Log evidence:**
```
2026-06-21 01:09:24 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-21 01:09:24 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1061ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-21 01:09:46
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted another out-of-schema label, 'force stage3'.

**Root cause:** The classifier invented a routing-style class name instead of one of the supported intents. It still fell back to others and escalated, so this did not break the turn.

**Suggested fix:** Add enum-constrained classifier output and reject or remap routing phrases before they become logged intent classes.

**Log evidence:**
```
2026-06-21 01:09:44 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-21 01:09:44 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1039ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-21 01:12:41
**User said:** use the source code as your guide

**Problem:** Stage 3 lost multi-turn context for a follow-up instruction.

**Root cause:** The user reply depends on the prior discussion, but the OpenAI brain was invoked with history=0 and file_ctx=False under the same session id. That means Stage 3 did not receive the previous turns or source-code context needed to interpret the instruction.

**Suggested fix:** Fix jane.proxy or the Stage 3 adapter to load conversation history by sid audit-178201, and attach relevant file context when the conversation is about source-code inspection.

**Log evidence:**
```
2026-06-21 01:09:46 INFO [jane.proxy] [audit-178201] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-21 01:12:41 INFO [jane.proxy] [audit-178201] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-21 01:12:41
**User said:** use the source code as your guide

**Problem:** Stage 1 classification latency was excessive for a short follow-up.

**Root cause:** The classifier spent 13.252 seconds before returning others:Low. That delay occurs before Stage 3 even starts.

**Suggested fix:** Add a short classifier timeout, for example 1-2 seconds, and default to others escalation when the local classifier is slow.

**Log evidence:**
```
2026-06-21 01:12:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (13252ms) params={}
```
```
2026-06-21 01:12:41 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-21 01:12:56
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 end-to-end latency was over 4 minutes, with repeated memory extractor timeouts.

**Root cause:** During the turn, short_term_extractor called the CLI LLM stack and hit three consecutive 45-second failures across primary and fallback models before the pipeline completed.

**Suggested fix:** Move short-term memory extraction off the user-visible response path, add a circuit breaker for repeated CLI LLM timeouts, and reduce fallback timeout budgets.

**Log evidence:**
```
2026-06-21 01:13:12 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-21 01:13:57 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-21 01:14:43 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-21 01:17:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (263755ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-21 01:17:44
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** A complex code/project request was routed to generic streaming Stage 3 and was cancelled after client disconnect.

**Root cause:** The request was treated as others:Low and sent to brain=OpenAI with history=0 and file_ctx=False. The brain kept running for over 11 minutes, the client disconnected, and the server cancelled execution before completion.

**Suggested fix:** Add a code_edit/project_work intent that routes to a durable Codex job with workspace context, progress updates, and continuation after HTTP client disconnect.

**Log evidence:**
```
2026-06-21 01:17:39 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-21 01:17:40 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-21 01:17:41 INFO [jane.proxy] [audit-178201] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-21 01:28:46 INFO [jane.proxy] [audit-178201] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-21 01:28:47 WARNING [jane.proxy] [audit-178201] Brain execution cancelled (stream) after 662184ms — likely client disconnect or timeout.
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-06-21 06:47:40
**User said:** [no transcripted user turn; briefing media fetch]

**Problem:** Briefing image/audio requests were rate-limited in a burst.

**Root cause:** The same client IP hit many /api/briefing/image and /api/briefing/audio endpoints within seconds, triggering the API rate limiter.

**Suggested fix:** Batch or throttle briefing media fetches on Android, and consider a separate rate-limit bucket for cached briefing assets.

**Log evidence:**
```
2026-06-21 06:47:40 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/image/1c6967a11253 (api)
```
```
2026-06-21 06:47:40 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/audio/0ece099b3c29/brief (api)
```
```
2026-06-21 06:48:00 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/saved (api)
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-06-21 17:49:48
**User said:** [no transcripted user turn; Standing Brain startup]

**Problem:** Stage 3 Standing Brain startup failed.

**Root cause:** Codex app-server could not initialize sqlite state under /home/chieh/.codex because the database was locked.

**Suggested fix:** Ensure only one Standing Brain process initializes the shared Codex sqlite state at a time, add startup locking/backoff, and configure sqlite busy_timeout or isolated CODEX_HOME per concurrent process.

**Log evidence:**
```
2026-06-21 17:49:48 ERROR [jane.web] Standing Brain startup failed: Codex app-server stdout closed. Error: failed to initialize sqlite state runtime under /home/chieh/.codex: failed to initialize state runtime at /home/chieh/.codex: error returned from database: (code: 5) database is locked
```

---

