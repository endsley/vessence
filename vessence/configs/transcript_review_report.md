# Transcript Quality Review — 2026-06-17

Generated: 2026-06-18 01:31:54

## Issue 1 [LOW]

**Turn:** 2026-06-17 01:09:45
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported class label before falling back to others.

**Root cause:** The classifier produced 'web automation', which is not in the registered class enum, so the pipeline mapped it to others. Routing still escalated to Stage 3, but the classifier prompt/schema is not constrained tightly enough.

**Suggested fix:** Constrain classifier output with an enum/JSON schema or add deterministic post-processing tests that reject unknown labels before release.

**Log evidence:**
```
2026-06-17 01:09:43 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-17 01:09:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (926ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-17 01:10:01
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted another unsupported class label before falling back to others.

**Root cause:** The classifier produced 'force stage3', which is not a registered class. The fallback routed correctly, but this shows the classifier is inventing routing labels.

**Suggested fix:** Make the Stage 1 decoder validate against the registry enum and log the original model output as a metric; tune examples so meta/system questions classify as others directly.

**Log evidence:**
```
2026-06-17 01:09:59 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-17 01:09:59 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1500ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-17 01:12:46
**User said:** use the source code as your guide

**Problem:** Stage 3 received no conversation history for a context-dependent follow-up.

**Root cause:** The same audit session had prior turns, but stream_message logged history=0. This makes short follow-ups like this lose the preceding Waterlily/source-code context.

**Suggested fix:** Fix stage3_escalate/session plumbing so sid_override preserves and loads the conversation history; add a regression test where a same-session follow-up reaches Stage 3 with nonzero history.

**Log evidence:**
```
2026-06-17 01:12:46 INFO [jane.proxy] [audit-178167] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```
```
2026-06-17 01:12:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (10300ms)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-17 01:12:46
**User said:** use the source code as your guide

**Problem:** Stage 1 classification took 34 seconds.

**Root cause:** The classifier path stalled around a heartbeat failure before finally returning others:Low. A fast-path classifier should not block this long.

**Suggested fix:** Add a hard Stage 1 timeout around the local classifier, fall back to others immediately on timeout, and emit model health metrics.

**Log evidence:**
```
2026-06-17 01:12:44 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-06-17 01:12:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (34395ms) params={}
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-17 01:13:00
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 took almost four minutes to complete.

**Root cause:** The configured brain path hit serial CLI timeouts and fallback failures, stretching end-to-end latency to 229394ms.

**Suggested fix:** Health-check CLI backends before routing, lower per-backend timeouts for interactive turns, and stop serial fallback chains once the user-facing latency budget is exceeded.

**Log evidence:**
```
2026-06-17 01:13:42 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-17 01:13:44 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-17 01:16:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (229394ms)
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-06-17 01:17:04
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Complex Stage 3 request took over ten minutes.

**Root cause:** The request escalated to Stage 3, then the primary and fallback CLI brains timed out serially; memory extraction also timed out. End-to-end latency was 605838ms.

**Suggested fix:** Move long coding/project work to an asynchronous job with progress updates, and keep the interactive Stage 3 response bounded by a strict latency budget.

**Log evidence:**
```
2026-06-17 01:17:36 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-17 01:18:21 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-17 01:19:07 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI timed out after 45s...
```
```
2026-06-17 01:27:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (605838ms)
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-06-17 12:42:17
**User said:** background Android message sync / briefing asset fetch

**Problem:** Android client API calls were rate-limited, including message sync.

**Root cause:** A burst of briefing audio/image requests from the same mobile IP exhausted the API limiter, and /api/messages/sync was rate-limited in the same window.

**Suggested fix:** Use separate rate-limit buckets for authenticated Android sync and briefing media, cache/dedupe briefing assets on the client, and add client backoff on 429.

**Log evidence:**
```
2026-06-17 12:42:02 WARNING [jane.web] Rate limited 172.56.199.190 on /api/briefing/audio/972d21e4d72e/brief (api)
```
```
2026-06-17 12:42:17 WARNING [jane.web] Rate limited 172.56.199.190 on /api/messages/sync (api)
```

---

## Issue 8 [LOW]

**Turn:** 2026-06-17 12:52:11
**User said:** get time request

**Problem:** A single voice request appears to have been processed more than once.

**Root cause:** Android logged one nonempty send at 12:52:11, but the server logged multiple get time Stage 1/Stage 2 executions and duplicate persistence workers seconds apart.

**Suggested fix:** Attach a request id/idempotency key from Android through the pipeline and drop duplicate in-flight requests for the same final STT result.

**Log evidence:**
```
2026-06-17T12:52:11.059Z [voice_flow] voice_flow[send_message] text_len=15 fromVoice=True
```
```
2026-06-17 12:52:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 get time:Very High (4515ms) params={}
```
```
2026-06-17 12:52:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 get time:Very High (9259ms) params={}
```
```
2026-06-17 12:52:15 INFO [jane.proxy] [codex-debug-] Persistence worker started stage=stage2 cls=get time user_chars=16 assistant_chars=31
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-06-17 13:05:31
**User said:** <class_protocol name="read_messages">

**Problem:** Audit transcript logged the internal class protocol as the user message.

**Root cause:** The recorded user turn contains the Stage 3 class contract wrapper instead of the raw Android utterance, which makes later quality auditing lose the actual spoken request.

**Suggested fix:** Store raw_user_text and stage3_prompt separately; transcript/audit exports should show raw_user_text and include protocol metadata only in a separate field.

**Log evidence:**
```
[2026-06-17 13:05:31] (jane_android) <class_protocol name="read_messages">
```
```
2026-06-17 13:05:29 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read messages:Very High voice=False prompt_len=6145 sid_override=True class_protocol=loaded:read_messages
```

---

## Issue 10 [CRITICAL]

**Turn:** 2026-06-17 13:05:31
**User said:** read messages request

**Problem:** Stage 2 read messages handler failed its response contract and escalated unnecessarily.

**Root cause:** Stage 1 correctly classified read messages with Very High confidence, but the handler returned an invalid shape. The provided Android diagnostics show no tool_handler execution afterward.

**Suggested fix:** Fix the read messages handler to return the registered Stage 2 envelope and CLIENT_TOOL marker directly; add schema validation tests for all deterministic handlers.

**Log evidence:**
```
2026-06-17 13:05:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read messages:Very High (1465ms) params={'filter_sender': None, 'unread_only': True, 'limit': None}
```
```
2026-06-17 13:05:18 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'read messages' returned invalid shape → Stage 3
```
```
2026-06-17 13:05:29 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read messages:Very High voice=False prompt_len=6145 sid_override=True class_protocol=loaded:read_messages
```

---

## Issue 11 [CRITICAL]

**Turn:** 2026-06-17 13:06:20
**User said:** read messages request

**Problem:** Repeated read messages request hit the same Stage 2 contract failure.

**Root cause:** The second read messages turn classified correctly, but the same handler again returned an invalid shape and forced Stage 3 instead of executing the deterministic phone-message flow.

**Suggested fix:** Block deployment when a registered handler returns an invalid shape for a golden-path utterance; this should fail CI instead of falling through to Stage 3.

**Log evidence:**
```
2026-06-17 13:06:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read messages:Very High (2000ms) params={'filter_sender': None, 'unread_only': True, 'limit': None}
```
```
2026-06-17 13:06:18 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'read messages' returned invalid shape → Stage 3
```
```
2026-06-17 13:06:19 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read messages:Very High voice=False prompt_len=6116 sid_override=True class_protocol=loaded:read_messages
```

---

## Issue 12 [CRITICAL]

**Turn:** 2026-06-17 13:06:41
**User said:** follow-up utterance after read messages

**Problem:** Android captured a follow-up STT result but did not send it to the server.

**Root cause:** The sentence_tts relaunch path produced stt_result text_len=11, but there is no following voice_flow[send_message] event.

**Suggested fix:** In the sentence_tts relaunch STT completion path, enqueue every nonempty final result and add a diagnostic error when stt_result is not followed by send_message.

**Log evidence:**
```
2026-06-17T13:06:38.633Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-06-17T13:06:41.111Z [voice_flow] voice_flow[stt_result] text_len=11
```
```
2026-06-17T13:06:43.388Z [wakeword] Model loaded: hey_jane.onnx
```

---

## Issue 13 [CRITICAL]

**Turn:** 2026-06-17 15:10:12
**User said:** read messages request

**Problem:** Read messages remained broken later in the day.

**Root cause:** Stage 1 again classified correctly, but the read messages handler still returned an invalid shape and escalated to Stage 3.

**Suggested fix:** Patch the read messages deterministic handler and add a startup self-test that invokes every class handler with representative params and verifies the response envelope.

**Log evidence:**
```
2026-06-17 15:10:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read messages:Very High (2792ms) params={'filter_sender': None, 'unread_only': True, 'limit': None}
```
```
2026-06-17 15:10:10 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'read messages' returned invalid shape → Stage 3
```
```
2026-06-17 15:10:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read messages:Very High voice=False prompt_len=6080 sid_override=True class_protocol=loaded:read_messages
```

---

## Issue 14 [CRITICAL]

**Turn:** 2026-06-17 15:11:13
**User said:** send message request

**Problem:** Stage 2 send message handler failed its response contract.

**Root cause:** Stage 1 correctly classified send message with Very High confidence, but after about 15 seconds the handler returned an invalid shape and forced Stage 3. The provided Android diagnostics show no tool_handler draft/send execution.

**Suggested fix:** Fix the send message handler to return a valid pending confirmation/draft envelope with CLIENT_TOOL sms_draft; add contract tests for missing recipient, resolved recipient, and confirmation flows.

**Log evidence:**
```
2026-06-17 15:10:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1275ms) params={}
```
```
2026-06-17 15:11:10 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-06-17 15:11:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=send message:Very High voice=False prompt_len=3543 sid_override=True class_protocol=loaded:send_message
```

---

## Issue 15 [CRITICAL]

**Turn:** 2026-06-17 15:11:34
**User said:** follow-up utterance after send message

**Problem:** Android captured a follow-up STT result but dropped it.

**Root cause:** The client relaunched STT after TTS, received stt_result text_len=11, then did not log send_message before returning to wakeword.

**Suggested fix:** Unify wakeword-launched and sentence_tts-relaunched STT completion handling so nonempty final transcripts always call the same send path.

**Log evidence:**
```
2026-06-17T15:11:31.610Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-06-17T15:11:34.169Z [voice_flow] voice_flow[stt_result] text_len=11
```
```
2026-06-17T15:11:36.937Z [wakeword] Model loaded: hey_jane.onnx
```

---

