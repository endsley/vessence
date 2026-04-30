# Transcript Quality Review — 2026-04-29

Generated: 2026-04-30 01:38:29

## Issue 1 [MEDIUM]

**Turn:** 2026-04-29 09:04:54
**User said:** currently how does your short-term memory work

**Problem:** Memory/thematic persistence failed on the same turn the user asked about short-term memory.

**Root cause:** Stage 3 answered the question, but the post-turn memory pipeline immediately failed because `memory.v1.conversation_manager` depends on a `claude` CLI binary that was not present. That means thematic classification and summary for this turn were not written, so the system was describing memory behavior while part of the memory path was already broken.

**Suggested fix:** Remove the hard dependency on the external `claude` executable for thematic classification/summary. Use the configured provider API directly, or detect the missing binary at startup and fall back cleanly.

**Log evidence:**
```
2026-04-29 09:04:54 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=46 sid_override=True class_protocol=n/a
```
```
2026-04-29 09:06:23 WARNING [memory.v1.conversation_manager] Theme classification LLM failed: CLI not found: claude
```
```
2026-04-29 09:06:23 WARNING [memory.v1.conversation_manager] Theme summary LLM failed: CLI not found: claude
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-29 09:07:14
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a g

**Problem:** Internal class-protocol text leaked into the recorded user turn, and the greeting fast path failed.

**Root cause:** The Android client only captured a 9-character utterance, but Stage 3 was sent a 1,142-character prompt with `class_protocol=loaded:greeting`, and that wrapper text appears in the transcript as the user message. In the same turn, the greeting handler returned `invalid shape`, forcing an unnecessary Stage 3 escalation.

**Suggested fix:** Keep raw user text separate from Stage 3 prompt scaffolding in persistence/history/TTS, and add schema-contract tests so the greeting handler always returns a valid Stage 2 response.

**Log evidence:**
```
2026-04-29T09:07:12.030Z [voice_flow] voice_flow[stt_result] text_len=9
```
```
2026-04-29 09:07:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (711ms) params={}
```
```
2026-04-29 09:07:13 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-04-29 09:07:14 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 3 [LOW]

**Turn:** 2026-04-29 09:16:09
**User said:** I think the memory that we have has the short-term and we also have a first in 

**Problem:** The classifier emitted an out-of-schema label (`force stage3`) instead of a registered intent.

**Root cause:** The Stage 1 classifier returned `force stage3`, which is not a valid class. The pipeline recovered by mapping it to `others:Low`, but this makes classifier telemetry unreliable and shows the classifier output is not properly constrained to the supported enum.

**Suggested fix:** Constrain classifier decoding to the allowed label set, or add a parser that translates control labels like `force stage3` before scoring/logging them.

**Log evidence:**
```
2026-04-29 09:16:08 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-04-29 09:16:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (816ms) params={}
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-29 09:20:53
**User said:** can you hook that back up

**Problem:** A technical/product-debugging request was misclassified as `send message`, sending the turn into the SMS flow.

**Root cause:** Stage 1 labeled the utterance `send message:Very High` and extracted a message body even though there was no recipient and the surrounding conversation was about Jane's memory pipeline. Stage 2 then failed with `handler 'send message' returned invalid shape`, so Stage 3 received the wrong class protocol and the conversation derailed into messaging behavior.

**Suggested fix:** Tighten `send message` intent gating so it requires an explicit messaging verb plus a plausible contact/recipient, and down-rank it when the utterance refers to system behavior or follows a technical discussion. Also make the handler return a structured clarify/escalate object instead of `invalid shape`.

**Log evidence:**
```
2026-04-29T09:20:51.262Z [voice_flow] voice_flow[stt_result] text_len=30
```
```
2026-04-29 09:20:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1283ms) params={'recipient': None, 'body': 'can you hook that back up', 'intent_kind': 'ask', 'confirm_signal': None}
```
```
2026-04-29 09:20:52 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-04-29 09:20:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=send message:Very High voice=False prompt_len=3688 sid_override=True class_protocol=loaded:send_message
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-04-29 09:21:27
**User said:** I love you

**Problem:** Follow-up routing did not stay in a structured clarification flow; the next short reply was reclassified from scratch and hit the same broken `send message` path again.

**Root cause:** After the previous send-message turn failed in Stage 2, there is no sign that a pending action captured the missing slots. The next 10-character reply went back through Stage 1, was classified again as `send message`, and Stage 2 again returned `invalid shape`. That indicates the pending-action resolver did not own the clarification loop.

**Suggested fix:** When `send message` is missing recipient/body/confirmation, persist a `pending_action` with required slots and bypass Stage 1 on the next turn. Add cancellation logic when the user redirects back to code/debugging.

**Log evidence:**
```
2026-04-29 09:20:52 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-04-29T09:21:24.851Z [voice_flow] voice_flow[stt_result] text_len=10
```
```
2026-04-29 09:21:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1254ms) params={'recipient': None, 'body': 'I love you', 'intent_kind': 'send', 'confirm_signal': None}
```
```
2026-04-29 09:21:26 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-04-29 09:22:04
**User said:** no I actually want you to write the code to fix this right now

**Problem:** The correction turn got trapped behind a long-running Stage 3 call, and a later voice request timed out with an empty reply.

**Root cause:** This turn escalated to Stage 3, but the persistent Claude session kept running for over 210 seconds. When the user spoke again at 09:24, the proxy could not acquire the request gate within 90 seconds and failed the request to avoid desync. The Android client then logged `relaunch_skipped ... reason=empty_reply`, so the user effectively got no response. The pipeline does not cancel or preempt an in-flight Stage 3 turn on barge-in/new input.

**Suggested fix:** Add interrupt/cancel support for the standing-brain session when a new user turn arrives, and enforce a server-side timeout that returns a fallback spoken reply instead of leaving the client with `empty_reply`.

**Log evidence:**
```
2026-04-29 09:22:04 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=62 sid_override=True class_protocol=n/a
```
```
2026-04-29 09:24:03 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=52 sid_override=True class_protocol=n/a
```
```
2026-04-29 09:25:33 WARNING [jane.proxy] [jane_android] Session request_gate timed out after 90s (stream) — failing request to prevent desync
```
```
2026-04-29T09:25:33.233Z [voice_flow] voice_flow[relaunch_skipped] path=onSendComplete reason=empty_reply
```
```
2026-04-29 09:25:35 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 10 complete in 210752ms (999 chars, 2 raw events)
```

---

