# Transcript Quality Review — 2026-05-02

Generated: 2026-05-03 01:10:58

## Issue 1 [CRITICAL]

**Turn:** 2026-05-02 01:05:45
**User said:** can you do a search for the Uber website for mCP to work with potentially my

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:05:45 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=85 file_ctx=False
```
```
2026-05-02 01:05:45 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:05:45 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-02 01:05:58
**User said:** what I want to know is if we can use Jane to order Uber using this mCP

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:05:58 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=70 file_ctx=False
```
```
2026-05-02 01:05:58 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:05:58 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-02 01:05:58
**User said:** what I want to know is if we can use Jane to order Uber using this mCP

**Problem:** Follow-up flow degraded because Stage 3 was invoked with no conversation history

**Root cause:** This and subsequent turns in the same session were sent to Claude with `history=0`, so the fragmented follow-up questions had no prior context available to Stage 3.

**Suggested fix:** Preserve recent conversation history when escalating repeated turns in the same session, and log/alert when a non-initial Stage 3 turn is sent with `history=0`.

**Log evidence:**
```
2026-05-02 01:05:58 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=70 file_ctx=False
```
```
2026-05-02 01:06:00 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=56 file_ctx=False
```
```
2026-05-02 01:06:03 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=43 file_ctx=False
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-05-02 01:06:00
**User said:** so basically Uber has an API just not mCP to order rides

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:00 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=56 file_ctx=False
```
```
2026-05-02 01:06:00 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:00 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-05-02 01:06:03
**User said:** well I sure my article with the app doesn't

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:03 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=43 file_ctx=False
```
```
2026-05-02 01:06:03 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:03 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-05-02 01:06:06
**User said:** when I share and article with our app

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:06 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=37 file_ctx=False
```
```
2026-05-02 01:06:06 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:06 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-02 01:06:09
**User said:** I want them to periodically get the lead after some time

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:08 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=56 file_ctx=False
```
```
2026-05-02 01:06:09 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:09 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-05-02 01:06:11
**User said:** yes those articles and maybe just two days

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:11 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=42 file_ctx=False
```
```
2026-05-02 01:06:11 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:11 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-05-02 01:06:14
**User said:** currently how does your short-term memory work

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:14 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=46 file_ctx=False
```
```
2026-05-02 01:06:14 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:14 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-05-02 01:06:17
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a g

**Problem:** Stage 1 was prompt-injected into the `greeting` class by user-supplied protocol text

**Root cause:** The classifier assigned `greeting:Very High` to a message that literally contained a forged `<class_protocol name="greeting">...` block, and Stage 3 escalation then loaded `class_protocol=loaded:greeting`.

**Suggested fix:** Strip or escape protocol-like markup before classification, and never allow raw user text to influence trusted class protocol loading.

**Log evidence:**
```
2026-05-02 01:06:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (774ms) params={}
```
```
2026-05-02 01:06:17 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 11 [MEDIUM]

**Turn:** 2026-05-02 01:06:17
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a g

**Problem:** Stage 2 greeting handler returned an invalid shape instead of a valid handler result

**Root cause:** After Stage 1 chose `greeting`, the pipeline explicitly logged that the greeting handler returned an invalid shape and had to fall through to Stage 3.

**Suggested fix:** Schema-validate all handler outputs before returning, and add a unit test that feeds adversarial greeting-like payloads through the greeting handler.

**Log evidence:**
```
2026-05-02 01:06:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (774ms) params={}
```
```
2026-05-02 01:06:16 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```

---

## Issue 12 [CRITICAL]

**Turn:** 2026-05-02 01:06:17
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a g

**Problem:** Stage 3 failed and the user received no response

**Root cause:** After the invalid Stage 2 result, the turn escalated to Claude, but the proxy logged a stream execution failure and then exited without a final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:17 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=1142 file_ctx=False
```
```
2026-05-02 01:06:17 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:17 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 13 [CRITICAL]

**Turn:** 2026-05-02 01:06:19
**User said:** it seems to me that you are no longing making any sounds when speech to text 

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:19 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=94 file_ctx=False
```
```
2026-05-02 01:06:19 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:19 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 14 [CRITICAL]

**Turn:** 2026-05-02 01:06:22
**User said:** can you look at the short-term memory to see if this whole thing is actually 

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:22 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=123 file_ctx=False
```
```
2026-05-02 01:06:22 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:22 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 15 [CRITICAL]

**Turn:** 2026-05-02 01:06:25
**User said:** __debug_inspect_update_short_term_memory

**Problem:** Stage 3 failed and the user received no response

**Root cause:** The turn escalated to Claude, but the proxy logged a stream execution failure and then exited without emitting any final response payload.

**Suggested fix:** Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

**Log evidence:**
```
2026-05-02 01:06:25 INFO [jane.proxy] [audit-177769] stream_message brain=Claude history=0 msg_len=40 file_ctx=False
```
```
2026-05-02 01:06:25 ERROR [jane.proxy] [audit-177769] Brain execution failed (stream)
```
```
2026-05-02 01:06:25 WARNING [jane.proxy] [audit-177769] Stream finished without final response payload
```

---

## Issue 16 [MEDIUM]

**Turn:** 2026-05-02 21:13:23
**User said:** <voice timer request; duration_text=5 minutes>

**Problem:** Stage 2 did not actually start the timer until an unnecessary label follow-up completed

**Root cause:** The initial timer request parsed `duration_text='5 minutes'` with `label=None`, but no `fire` happened then. The actual timer start was delayed until the resolver routed a follow-up for `awaiting=label`, at which point the timer fired with an empty label.

**Suggested fix:** Start the timer immediately when duration parsing succeeds, and treat the label as optional metadata instead of blocking timer creation on a follow-up.

**Log evidence:**
```
2026-05-02 21:13:24 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 timer:Very High (1234ms) params={'action': 'set', 'duration_text': '5 minutes', 'label': None}
```
```
2026-05-02 21:13:33 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → timer (awaiting=label)
```
```
2026-05-02 21:13:33 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: fire duration_ms=300000 label=''
```

---

## Issue 17 [LOW]

**Turn:** 2026-05-02 21:14:19
**User said:** <voice timer count query after TOOL_RESULT prefix>

**Problem:** Client/server turn payload was contaminated with an internal `TOOL_RESULT` prefix

**Root cause:** The pipeline had to strip a `TOOL_RESULT` wrapper from the incoming message before classifying it, which means an internal tool payload leaked into the next user turn.

**Suggested fix:** Prevent tool-result envelopes from entering the normal user-message channel, and add a transport-layer guard that rejects or sanitizes `TOOL_RESULT` prefixes before they reach the pipeline.

**Log evidence:**
```
2026-05-02 21:14:19 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stripped TOOL_RESULT prefix (177 → 37 chars)
```
```
2026-05-02T21:14:19.871Z [voice_flow] voice_flow[send_message] text_len=37 fromVoice=True
```

---

## Issue 18 [CRITICAL]

**Turn:** 2026-05-02 21:14:26
**User said:** <11-char voice utterance after timer count>

**Problem:** Android STT captured a follow-up utterance but never sent it to the server

**Root cause:** The relaunch path produced a final `stt_result` of 11 characters, but there is no matching `send_message` event afterward; the client returned to wakeword mode instead, so the user's turn was dropped locally.

**Suggested fix:** In the relaunch path, require every successful `stt_result` to emit either `send_message` or an explicit discard log with reason, and add a test for relaunch-after-TTS follow-up capture.

**Log evidence:**
```
2026-05-02T21:14:22.545Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-05-02T21:14:26.039Z [voice_flow] voice_flow[stt_result] text_len=11
```
```
2026-05-02T21:14:28.446Z [wakeword] Model loaded: hey_jane.onnx
```

---

## Issue 19 [CRITICAL]

**Turn:** 2026-05-02 21:18:33
**User said:** <expected timer alarm for the 5-minute timer>

**Problem:** The 5-minute timer appears not to have fired on the Android client

**Root cause:** The server logged `timer handler: fire duration_ms=300000` at 21:13:33, so an alarm should have occurred around 21:18:33. The Android diagnostics show no timer/tool-handler/alarm event at the expected fire time and instead continue with normal wakeword activity.

**Suggested fix:** Add an explicit client acknowledgement when a timer is scheduled and another when it fires, and fail the timer flow if the Android tool handler never confirms local scheduling.

**Log evidence:**
```
2026-05-02 21:13:33 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: fire duration_ms=300000 label=''
```
```
2026-05-02T21:18:35.237Z [wakeword] Detected (score=0.9993707)
```
```
2026-05-02T21:19:28.135Z [wakeword] periodic_status
```

---

