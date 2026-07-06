# Transcript Quality Review — 2026-07-05

Generated: 2026-07-06 01:41:36

## Issue 1 [LOW]

**Turn:** 2026-07-05 01:20:03
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported class before falling back to others.

**Root cause:** The classifier returned `force stage3`, which is outside the accepted class set. The wrapper coerced it to `others:Low`, so routing was acceptable but the classifier schema contract is loose.

**Suggested fix:** Constrain Stage 1 to the allowed enum with structured decoding, or explicitly normalize stage3-forcing aliases before logging and metrics.

**Log evidence:**
```
2026-07-05 01:20:00 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-05 01:20:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1207ms) params={}
```
```
2026-07-05 01:20:02 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-05 01:20:27
**User said:** use the source code as your guide

**Problem:** The follow-up was sent to Stage 3 without prior conversation or source context.

**Root cause:** The same audit session invoked Stage 3 with `history=0` and `file_ctx=False`, so this contextual follow-up was handled as an isolated prompt instead of being tied to the prior architecture question and grounded in source code.

**Suggested fix:** Persist and pass conversation history for `sid_override` sessions, and attach repo/source context or route to a code-aware Stage 3 path when the user asks to use source code.

**Log evidence:**
```
2026-07-05 01:20:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1612ms) params={}
```
```
2026-07-05 01:20:26 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-07-05 01:20:27 INFO [jane.proxy] [audit-178322] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-07-05 01:22:17
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 1 classification latency was extremely high.

**Root cause:** The Stage 1 classifier took 65072ms before falling back to `others:Low`, which is far beyond a fast-path classifier budget.

**Suggested fix:** Add a hard timeout around Stage 1, fall back to `others:Low` within a small latency budget, and investigate the classifier backend stall.

**Log evidence:**
```
2026-07-05 01:21:25 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-07-05 01:22:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (65072ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-07-05 01:22:17
**User said:** please familiarize yourself with the waterlily project

**Problem:** Project familiarization was invoked without visible project/source context.

**Root cause:** Stage 3 was called with `history=0` and `file_ctx=False` for a project-specific request. The logs do not show code context being attached before the OpenAI brain was streamed.

**Suggested fix:** For project-specific requests, route Stage 3 through the local code-agent path or attach indexed repo context before generation.

**Log evidence:**
```
2026-07-05 01:22:17 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-07-05 01:22:17 INFO [jane.proxy] [audit-178322] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-07-05 01:24:33 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (136529ms)
```

---

## Issue 5 [LOW]

**Turn:** 2026-07-05 01:24:39
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 emitted another unsupported class before falling back to others.

**Root cause:** The classifier returned `web automation`, which is not in the accepted taxonomy. It was coerced to `others:Low` and escalated.

**Suggested fix:** Either add a first-class code/project-work category or teach the classifier to map implementation requests directly to the valid Stage 3 escalation label.

**Log evidence:**
```
2026-07-05 01:24:37 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-05 01:24:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1448ms) params={}
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-07-05 01:24:39
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to complete the user request and was cancelled after about 15 minutes.

**Root cause:** The Stage 3 stream stayed active for 922217ms, the client disconnected, and the brain execution was cancelled. The logs show no successful Stage 3 completion for the requested site-wide mobile UI work.

**Suggested fix:** Move long code tasks to a background job with progress events and resumable client state, enforce Stage 3 execution budgets, and avoid cancelling useful work solely because the streaming client disconnects.

**Log evidence:**
```
2026-07-05 01:24:39 INFO [jane.proxy] [audit-178322] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-07-05 01:40:00 INFO [jane.proxy] [audit-178322] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-05 01:40:00 WARNING [jane.proxy] [audit-178322] Brain execution cancelled (stream) after 921061ms — likely client disconnect or timeout. Stack:
```
```
2026-07-05 01:40:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (922217ms)
```

---

