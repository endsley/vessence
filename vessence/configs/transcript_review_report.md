# Transcript Quality Review — 2026-06-23

Generated: 2026-06-24 01:33:19

## Issue 1 [LOW]

**Turn:** 2026-06-23 01:13:46
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 classifier produced an unsupported intent label, then coerced it to others.

**Root cause:** The classifier model returned 'web automation', which is outside the allowed taxonomy. The fallback to others was safe for this turn, but the warning shows classifier/schema drift.

**Suggested fix:** Constrain Stage 1 decoding to the supported enum or add an explicit postprocessor mapping unsupported stage3-style labels to others without warning noise.

**Log evidence:**
```
2026-06-23 01:13:45 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-23 01:13:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1357ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-23 01:14:06
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 classifier produced another unsupported intent label.

**Root cause:** The classifier returned 'force stage3', which is not a valid category. It was coerced to others and escalated, so routing was acceptable but classifier output is not protocol-compliant.

**Suggested fix:** Update the classifier prompt/schema so it cannot emit meta-labels like 'force stage3'; use a fixed enum or validated JSON schema.

**Log evidence:**
```
2026-06-23 01:14:03 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-23 01:14:03 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (986ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-23 01:14:36
**User said:** use the source code as your guide

**Problem:** Stage 1 took 14 seconds on a short follow-up utterance.

**Root cause:** The classifier completed as others:Low but only after 14028ms, delaying Stage 3 escalation for a simple contextual instruction.

**Suggested fix:** Add a short classifier deadline, for example 1500-2500ms, and escalate to Stage 3 on timeout for non-fast-path text.

**Log evidence:**
```
2026-06-23 01:14:35 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (14028ms) params={}
```
```
2026-06-23 01:14:36 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-23 01:14:36
**User said:** use the source code as your guide

**Problem:** Stage 3 follow-up context appears fragile because each OpenAI stream is logged with history=0.

**Root cause:** This turn depends on the prior question, but the proxy log shows no chat history attached at the Stage 3 boundary. The same pattern appears on surrounding turns.

**Suggested fix:** Verify sid_override actually binds to a persistent Stage 3 session; if not, pass recent conversation history into stream_message or persist it server-side by conversation id.

**Log evidence:**
```
2026-06-23 01:14:36 INFO [jane.proxy] [audit-178219] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```
```
2026-06-23 01:14:57 INFO [jane.proxy] [audit-178219] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-23 01:17:46
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Long Stage 3 task ran for about 15 minutes, the client disconnected, and the brain execution was cancelled.

**Root cause:** The request escalated to Stage 3, then the stream stayed active until the client disconnected at 01:32:55. The pipeline cancelled the brain after 908243ms, so the user likely did not receive a completed result.

**Suggested fix:** Move long coding tasks to a durable background job with progress events and reconnect support; keep the HTTP/WebSocket stream alive with heartbeats or return a job id immediately.

**Log evidence:**
```
2026-06-23 01:17:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-23 01:32:55 INFO [jane.proxy] [audit-178219] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-23 01:32:55 WARNING [jane.proxy] [audit-178219] Brain execution cancelled (stream) after 908243ms — likely client disconnect or timeout. Stack:
```
```
2026-06-23 01:32:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (912001ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-23 01:17:46
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Short-term memory extraction repeatedly timed out during the long Stage 3 turn.

**Root cause:** The primary LLM and two fallbacks each hit a 45s timeout, then short_term_extractor gave up. This likely added latency and lost memory capture for the conversation.

**Suggested fix:** Run short-term memory extraction off the user-facing path, cap total fallback time, and skip fallback chains when the active Stage 3 job is already long-running.

**Log evidence:**
```
2026-06-23 01:18:26 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-23 01:19:11 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-23 01:19:56 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-23 01:19:56 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```

---

