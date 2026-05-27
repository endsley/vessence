# Transcript Quality Review — 2026-05-26

Generated: 2026-05-27 01:38:02

## Issue 1 [MEDIUM]

**Turn:** 2026-05-26 01:25:50
**User said:** currently is your background large language model using Claude codex or call I mean

**Problem:** Stage 3 follow-up context was not preserved for the audit web session.

**Root cause:** The same session id audit-177977 repeatedly reached Stage 3 with history=0, even on later turns. Other sessions later in the day show history increasing, so this path is not loading or saving conversation history correctly.

**Suggested fix:** Make sid_override sessions use the same persistent conversation-history key as normal sessions, and add a regression test that repeated turns on one sid produce history > 0.

**Log evidence:**
```
2026-05-26 01:22:20 INFO [jane.proxy] [audit-177977] stream_message brain=OpenAI history=0 msg_len=68 file_ctx=False
```
```
2026-05-26 01:25:50 INFO [jane.proxy] [audit-177977] stream_message brain=OpenAI history=0 msg_len=105 file_ctx=False
```
```
2026-05-26 01:26:07 INFO [jane.proxy] [audit-177977] stream_message brain=OpenAI history=0 msg_len=94 file_ctx=False
```
```
2026-05-26 14:40:00 INFO [jane.proxy] [74230bbf74bb] stream_message brain=OpenAI history=4 msg_len=103 file_ctx=False
```

---

## Issue 2 [LOW]

**Turn:** 2026-05-26 01:27:50
**User said:** currently which large language model is being used as Jane Webb

**Problem:** Stage 1 emitted an invalid intent label before falling back to others.

**Root cause:** The classifier returned the non-enum class 'force stage3'. The fallback to others preserved routing, but the classifier contract is loose enough to produce unsupported labels.

**Suggested fix:** Constrain Stage 1 output to a strict enum or normalize escalation synonyms such as 'force stage3' to the supported escalation/others path before logging a warning.

**Log evidence:**
```
2026-05-26 01:27:49 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-26 01:27:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (991ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-26 08:08:45
**User said:** I'm currently you are using cold text as the third brain right

**Problem:** Android voice turns were treated as non-voice by the server Stage 3 path.

**Root cause:** The Android client sent fromVoice=True, but stage3_escalate logged voice=False for the same turns. That can make Stage 3 use text-mode behavior for spoken interactions.

**Suggested fix:** Propagate the Android fromVoice flag into the backend pipeline voice boolean and add an integration test covering Android STT-to-Stage3 routing.

**Log evidence:**
```
2026-05-26T08:08:43.080Z [voice_flow] voice_flow[send_message] text_len=62 fromVoice=True
```
```
2026-05-26 08:08:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=62 sid_override=True class_protocol=n/a
```
```
2026-05-26T08:09:16.482Z [voice_flow] voice_flow[send_message] text_len=12 fromVoice=True
```
```
2026-05-26 08:09:18 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=12 sid_override=True class_protocol=n/a
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-26 08:09:18
**User said:** codex timing

**Problem:** Android/background requests hit API rate limits immediately after the voice interaction.

**Root cause:** The same IP rapidly requested many briefing audio, image, and announcement endpoints within seconds, causing server-side rate limiting.

**Suggested fix:** Add client-side request coalescing, caching, and exponential backoff for briefing assets and announcements; tune route-specific rate limits so background media fetches do not interfere with assistant use.

**Log evidence:**
```
2026-05-26 08:10:41 WARNING [jane.web] Rate limited 172.56.195.120 on /api/briefing/audio/045ced2dfefa/brief (api)
```
```
2026-05-26 08:10:44 WARNING [jane.web] Rate limited 172.56.195.120 on /api/jane/announcements (api)
```
```
2026-05-26 08:10:50 WARNING [jane.web] Rate limited 172.56.195.120 on /api/briefing/image/fec9e17a3844 (api)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-05-26 14:40:00
**User said:** also, for each question please write a hint section that's helpful fo the student

**Problem:** Stage 3 work was cancelled before completing the requested education-project change.

**Root cause:** The stream logged a client disconnect and then cancelled the brain execution after about 54 seconds, despite first saying it would wait for the adapter task to finish.

**Suggested fix:** Shield long-running Stage 3 adapter tasks from HTTP stream cancellation, persist the final result for later retrieval, and only cancel when the user explicitly aborts.

**Log evidence:**
```
2026-05-26 14:39:59 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=103 sid_override=True class_protocol=n/a
```
```
2026-05-26 14:40:54 INFO [jane.proxy] [74230bbf74bb] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-05-26 14:40:54 WARNING [jane.proxy] [74230bbf74bb] Brain execution cancelled (stream) after 53811ms — likely client disconnect or timeout. Stack:
```
```
2026-05-26 14:40:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (54337ms)
```

---

