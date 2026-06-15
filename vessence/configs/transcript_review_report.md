# Transcript Quality Review — 2026-06-14

Generated: 2026-06-15 01:36:10

## Issue 1 [CRITICAL]

**Turn:** 2026-06-14 01:14:13
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 3 did not preserve multi-turn context for a same-session follow-up.

**Root cause:** The same audit session was used, and stage3_escalate had sid_override=True, but jane.proxy started each Stage 3 call with history=0. Follow-up turns therefore reached the frontier brain without prior conversation context.

**Suggested fix:** Hydrate Stage 3 history from the session id before stream_message and persist Stage 3 user/assistant turns immediately after completion. Add an integration test where two turns with the same sid produce history>0 on the second call.

**Log evidence:**
```
2026-06-14 01:12:50 INFO [jane.proxy] [audit-178141] stream_message brain=OpenAI history=0 msg_len=11 file_ctx=False
```
```
2026-06-14 01:14:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=56 sid_override=True class_protocol=n/a
```
```
2026-06-14 01:14:12 INFO [jane.proxy] [audit-178141] stream_message brain=OpenAI history=0 msg_len=56 file_ctx=False
```
```
2026-06-14 01:15:05 INFO [jane.proxy] [audit-178141] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-14 01:14:13
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported class and took 8.7 seconds before falling back to others.

**Root cause:** The classifier model returned 'web automation', which is outside the supported intent enum, so the classifier coerced it to others. The slow classifier path delayed escalation.

**Suggested fix:** Constrain classifier output to the supported enum in prompt/schema validation, map known aliases before warning, and enforce a short Stage 1 timeout with immediate others fallback.

**Log evidence:**
```
2026-06-14 01:14:11 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-14 01:14:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (8700ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-14 01:15:05
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported class and spent 28.9 seconds classifying a complex Stage 3 question.

**Root cause:** The classifier returned 'force stage3', another label outside the supported enum, then coerced to others after a long model call.

**Suggested fix:** Add strict enum decoding for Stage 1 and a fast rule that complex/meta questions route to others without waiting on a long classifier call.

**Log evidence:**
```
2026-06-14 01:15:01 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-14 01:15:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (28895ms) params={}
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-14 01:15:05
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** The Stage 3 turn started but has no matching completion log before the next user turn.

**Root cause:** stage3_escalate and stream_message ran for the 01:15:05 turn, but no corresponding 'Jane stream pipeline task finished' or 'stage3 end-to-end' line appears before the 01:16:29 turn began.

**Suggested fix:** Attach a request id to every Stage 3 escalation and log completion, cancellation, and errors in a finally block. Serialize or explicitly cancel overlapping Stage 3 turns for the same session.

**Log evidence:**
```
2026-06-14 01:15:05 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```
```
2026-06-14 01:15:05 INFO [jane.proxy] [audit-178141] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-14 01:16:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (23116ms) params={}
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-14 01:16:29
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 1 took 23.1 seconds to route an obvious Stage 3 project request.

**Root cause:** The classifier completed as others:Low, which was the right route, but the classifier latency dominated the fast-path decision.

**Suggested fix:** Add a cheap preclassifier/rule for project-work commands such as 'familiarize yourself', 'inspect', and 'go over' to route directly to Stage 3.

**Log evidence:**
```
2026-06-14 01:16:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (23116ms) params={}
```
```
2026-06-14 01:16:28 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-14 01:19:04
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 took almost 13 minutes to finish, with repeated LLM CLI fallback timeouts.

**Root cause:** The request escalated correctly, but the Stage 3 path did not finish until 777269ms later. During the turn, primary and fallback LLM calls timed out repeatedly, and short-term memory extraction also failed.

**Suggested fix:** Put a hard wall-clock budget on Stage 3 turns, stream progress/status for long code tasks, and move memory extraction/fallback chains fully out of the response path with shorter per-provider timeouts.

**Log evidence:**
```
2026-06-14 01:19:03 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-14 01:19:04 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-06-14 01:19:39 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-14 01:20:25 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-14 01:21:10 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-14 01:32:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (777269ms)
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-06-14 21:05:37
**User said:** unknown Android weather voice request, text_len=32

**Problem:** The weather fast path took 7.9 seconds even though it had no resolved location and left a follow-up pending.

**Root cause:** Stage 1 correctly classified weather with location=None, but the Stage 2 weather handler still ran for 7867ms before returning a response and pending follow-up.

**Suggested fix:** Short-circuit the weather handler when location is missing: ask the location follow-up immediately, or use a cached/default location before any slow external lookup.

**Log evidence:**
```
2026-06-14 21:05:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 weather:Very High (1271ms) params={'topic': 'forecast', 'day': 'tomorrow', 'location': None}
```
```
2026-06-14 21:05:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 weather handler (7867ms)
```
```
2026-06-14 21:05:59 INFO [jane_web.jane_v2.pending_action_resolver] resolver: global cancel matched for pending STAGE2_FOLLOWUP
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-06-14 21:06:21
**User said:** post-weather Android briefing media fetches

**Problem:** Android briefing image/audio requests were rate limited in a burst.

**Root cause:** The generic API rate limiter applied to multiple /api/briefing/image and /api/briefing/audio requests from the Android client IP, blocking media fetches shortly after the voice flow.

**Suggested fix:** Give authenticated/mobile briefing media endpoints a separate static-media rate limit, add client-side batching/caching, or raise the burst allowance for these asset URLs.

**Log evidence:**
```
2026-06-14 21:06:21 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/image/91c189e7852b (api)
```
```
2026-06-14 21:06:21 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/audio/461dd41e16b6/brief (api)
```
```
2026-06-14 21:06:21 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/audio/e8e0c274d3b2/brief (api)
```

---

