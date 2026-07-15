# Transcript Quality Review — 2026-07-14

Generated: 2026-07-15 00:06:33

## Issue 1 [MEDIUM]

**Turn:** 2026-07-14 17:53:12
**User said:** are you currently using a codex as the bottom layer

**Problem:** The voice response was delayed by a mid-turn brain-provider failure and failover.

**Root cause:** Stage 1 correctly escalated the technical question, but the configured Claude brain returned its organization spend-limit error. The proxy shut it down, switched Jane to Codex, and did not finish the Stage 3 pipeline until 13.451 seconds after escalation; the client relaunched STT about 23 seconds after sending the utterance.

**Suggested fix:** Run a provider-health or quota check before accepting a Stage 3 turn, immediately route to the known-working fallback when Claude is quota-exhausted, and avoid starting a doomed Claude request.

**Log evidence:**
```
2026-07-14 17:53:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1117ms) params={}
```
```
2026-07-14 17:53:14 WARNING [jane.proxy] [jane_android] Claude brain exhausted (You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit) - disconnecting Claude and switching Jane to Codex
```
```
2026-07-14 17:53:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (13451ms)
```
```
2026-07-14T17:53:31.874Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-07-14 21:12:08
**User said:** what is currently my speech to text Library

**Problem:** A straightforward configuration question took roughly 134 seconds from client submission to response playback.

**Root cause:** The request was appropriately classified as an unsupported fast-path intent and sent to Stage 3, but Stage 1 consumed 22.223 seconds and the OpenAI Stage 3 call consumed another 110.142 seconds. The client did eventually receive speech and relaunch STT, so this was server-side latency rather than client execution failure.

**Suggested fix:** Add a short Stage 1 timeout with immediate fallback to others, enforce Stage 3 first-token and total-response deadlines, and surface a brief progress acknowledgement when a source-code lookup exceeds the voice latency budget.

**Log evidence:**
```
2026-07-14T21:11:41.818Z [voice_flow] voice_flow[send_message] text_len=43 fromVoice=True
```
```
2026-07-14 21:12:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (22223ms) params={}
```
```
2026-07-14 21:12:06 INFO [jane.proxy] [jane_android] stream_message brain=OpenAI history=0 msg_len=43 file_ctx=False
```
```
2026-07-14 21:13:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (110142ms)
```
```
2026-07-14T21:13:55.506Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```

---

## Issue 3 [LOW]

**Turn:** 2026-07-14 23:45:27
**User said:** right now, you are using the same codex process for each prompt instead of spawn

**Problem:** Stage 1 emitted an invalid intent label.

**Root cause:** The classifier returned 'force stage3', which is outside the registered intent taxonomy. The classifier wrapper safely converted it to others with Low confidence, so routing still reached the appropriate Stage 3 path, but the model output contract was not enforced.

**Suggested fix:** Constrain classifier decoding to the registered intent enum or explicitly register an internal force-stage3 routing token and normalize it without logging it as an unknown class.

**Log evidence:**
```
2026-07-14 23:45:25 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-14 23:45:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (22593ms) params={}
```
```
2026-07-14 23:45:26 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-07-14 23:45:27
**User said:** right now, you are using the same codex process for each prompt instead of spawn

**Problem:** The answer required about 129 seconds of server processing.

**Root cause:** Stage 1 took 22.593 seconds before escalation, then the OpenAI Stage 3 path took 106.723 seconds. No Stage 2 work or client-side execution accounts for this delay.

**Suggested fix:** Apply a classifier timeout and cache the fallback-to-others decision; add first-token and overall deadlines to the OpenAI standing-brain request and emit a progress response for long source inspection.

**Log evidence:**
```
2026-07-14 23:45:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (22593ms) params={}
```
```
2026-07-14 23:45:27 INFO [jane.proxy] [audit-178408] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-07-14 23:47:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (106723ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-14 23:49:51
**User said:** please familiarize yourself with the waterlily project

**Problem:** The source-familiarization request spent over three minutes across classification and Stage 3 processing.

**Root cause:** The recorded Stage 1 classification alone took 51.083 seconds, and the subsequent OpenAI Stage 3 execution took 133.935 seconds. The logs prove both server stages exceeded an interactive latency budget; there was no Stage 2 fast path or client-side operation involved.

**Suggested fix:** Bypass intent classification for explicit repository-research commands, enforce classifier and Stage 3 deadlines, and acknowledge the request immediately before continuing lengthy repository inspection asynchronously.

**Log evidence:**
```
2026-07-14 23:48:46 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (51083ms) params={}
```
```
2026-07-14 23:49:51 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-07-14 23:49:51 INFO [jane.proxy] [audit-178408] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-07-14 23:52:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (133935ms)
```

---

## Issue 6 [LOW]

**Turn:** 2026-07-14 23:52:10
**User said:** currently, the waterlily site is web only meant for browsers on laptops and comp

**Problem:** Stage 1 emitted another unsupported intent label instead of a valid taxonomy value.

**Root cause:** Qwen returned 'web automation'. The wrapper mapped the unknown label to others with Low confidence, which correctly caused Stage 3 escalation, but this repeated the classifier output-contract failure seen earlier in the session.

**Suggested fix:** Use constrained enum decoding and add training examples mapping repository/UI implementation requests directly to others or a registered software-development intent.

**Log evidence:**
```
2026-07-14 23:52:09 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-14 23:52:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1399ms) params={}
```
```
2026-07-14 23:52:10 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```

---

