# Transcript Quality Review — 2026-06-07

Generated: 2026-06-08 01:34:22

## Issue 1 [MEDIUM]

**Turn:** 2026-06-07 01:10:42
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 routed a Web-automation request as generic `others` instead of a specific intent.

**Root cause:** Classifier emitted an unmapped label (`web automation`) and the runtime coerced it to `others:Low`, so no intent-specific path or specialized tool protocol could be selected.

**Suggested fix:** Add `web automation` (and aliases) to the stage-1 taxonomy and map it to a dedicated Stage 2/Stage 3 protocol instead of forcing it through `others`.

**Log evidence:**
```
2026-06-07 01:10:41 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-07 01:10:41 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (795ms) params={}
```
```
2026-06-07 01:10:42 INFO [jane.proxy] [audit-178080] stream_message brain=OpenAI history=0 msg_len=56 file_ctx=False
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-07 01:10:56
**User said:** right now, you are using the same codex process for each prompt instead of spawning a new one each time right

**Problem:** User intent to force a full Stage-3 path was not preserved as a recognized protocol (`force stage3` was downgraded).

**Root cause:** Classifier produced unknown class `force stage3` and pipeline logged `others:Low` with `class_protocol=n/a`, which means the explicit escalation intent never triggered a distinct handler/policy.

**Suggested fix:** Normalize phrases like `force stage3` in stage-1 to a dedicated class and explicitly bind that class to `class_protocol=loaded:delegate_opus` or equivalent escalation behavior.

**Log evidence:**
```
2026-06-07 01:10:55 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-07 01:10:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (665ms) params={}
```
```
2026-06-07 01:10:55 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-07 01:10:56
**User said:** right now, you are using the same codex process for each prompt instead of spawning a new one each time right

**Problem:** Turn spent ~90s in Stage 3 despite low-complexity clarification, creating severe UX degradation.

**Root cause:** After fallback to generic `others`, the request executed full stage-3 path with no fast-path/latency guard and no earlier completion, so response latency exceeded acceptable limits.

**Suggested fix:** Add a bounded Stage-3 budget (e.g., 20–30s) with progress updates and a deterministic fallback response if exceeded; route short operational requests to lighter handlers when confidence is low but intent is simple.

**Log evidence:**
```
2026-06-07 01:10:55 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```
```
2026-06-07 01:10:56 INFO [jane.proxy] [audit-178080] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-07 01:12:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (90253ms)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-07 01:12:30
**User said:** use the source code as your guide

**Problem:** Follow-up context appears not to be carried forward between turns; each Stage 3 call shows zero history.

**Root cause:** `stream_message` logs show `history=0` on follow-up turns, so resolver/context handoff is effectively not being provided to Stage 3 and follow-up flow depends on zero-shot context.

**Suggested fix:** Persist and pass conversation history for the same session in Stage 3 calls, and emit explicit pending-action resolver logs when it intercepts turn routing.

**Log evidence:**
```
2026-06-07 01:12:30 INFO [jane.proxy] [audit-178080] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```
```
2026-06-07 01:12:52 INFO [jane.proxy] [audit-178080] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-07 01:12:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (772ms) params={}
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-07 01:12:52
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 had a primary LLM timeout and fallback pressure before completion.

**Root cause:** Primary CLI LLM timed out after 45 seconds, forcing fallback handling and extending latency to 159s.

**Suggested fix:** Pre-warm or health-check LLM CLIs before request dispatch and enforce a shorter retry budget with immediate secondary model promotion to avoid long stalls.

**Log evidence:**
```
2026-06-07 01:12:52 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-07 01:13:11 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-07 01:15:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (159127ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-07 01:15:34
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers, I would like you to go over the entire site and when detected a mobile version

**Problem:** Stage 3 failed to return a completed response and the client disconnected mid-stream.

**Root cause:** After unknown-class fallback to `others`, all fallback LLMs timed out (`Primary`, then `gemini`, then `claude`), then the server logged client disconnect and brain execution cancellation, indicating an unrecoverable long-running stage-3 failure path.

**Suggested fix:** Add hard stage-3 timeouts and progressive fallback behavior; on repeated model timeouts, return a structured partial/error response and keep a resumable background job instead of keeping the stream open indefinitely.

**Log evidence:**
```
2026-06-07 01:15:33 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-07 01:15:34 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-07 01:16:16 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-07 01:17:01 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-07 01:17:46 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-07 01:28:34 WARNING [jane.proxy] [audit-178080] Brain execution cancelled (stream) after 779947ms — likely client disconnect or timeout.
```

---

