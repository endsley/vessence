# Transcript Quality Review — 2026-05-29

Generated: 2026-05-30 01:19:59

## Issue 1 [MEDIUM]

**Turn:** 2026-05-29 18:13:12
**User said:** unknown 16-character voice capture

**Problem:** Extra voice turn was processed as a greeting between two substantive UI-change requests.

**Root cause:** Android relaunched STT after the long Stage 3 response, captured a 16-character utterance, and sent it. The server classified it as greeting:Very High and handled it in Stage 2. This turn is not present in the chronological user transcript, so it appears to be an unintended relaunch/noise capture rather than a real user request.

**Suggested fix:** Add client-side suppression for very short post-TTS captures unless wakeword or explicit user speech confidence is present, and log the recognized text for all voice sends so audits can verify whether the turn was real.

**Log evidence:**
```
2026-05-29T18:12:31.878Z [voice_flow] voice_flow[stt_result] text_len=16
```
```
2026-05-29T18:12:31.878Z [voice_flow] voice_flow[send_message] text_len=16 fromVoice=True
```
```
2026-05-29 18:13:12 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (1339ms) params={}
```
```
2026-05-29 18:13:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 greeting handler (646ms)
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-29 18:13:25
**User said:** I feel like the header is still based on web browser

**Problem:** Stage 3 took nearly 8.3 minutes to complete a follow-up UI edit request.

**Root cause:** The turn correctly escalated as others:Low, but the Stage 3 stream ran from 18:13:23 to 18:21:39 with prompt_len=667/history=2. No Stage 2 fast path or progress handling exists for ongoing code-edit follow-ups, so the voice conversation stalled for 497639ms.

**Suggested fix:** For code-edit/project modification intents, route to a dedicated async job handler that immediately acknowledges, streams progress, and keeps the voice client from waiting on the full frontier-brain execution.

**Log evidence:**
```
2026-05-29 18:13:21 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2890ms) params={}
```
```
2026-05-29 18:13:23 INFO [jane.proxy] [jane_android] stream_message brain=OpenAI history=2 msg_len=667 file_ctx=False
```
```
2026-05-29 18:21:39 INFO [jane.proxy] [jane_android] Jane stream pipeline task finished
```
```
2026-05-29 18:21:39 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (497639ms)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-29 18:21:54
**User said:** I feel like the header for the red not the web view but the and

**Problem:** Voice follow-up appears truncated or garbled, but was still sent to Stage 3.

**Root cause:** Android relaunched STT after sentence TTS, began recognition at 18:21:50, then the transcript shows an incomplete utterance. The server escalated the malformed text to Stage 3 with history=4 instead of asking for clarification.

**Suggested fix:** Add a voice-input quality gate for low-confidence, incomplete, or syntactically broken STT results. For code-edit follow-ups, ask a short clarification instead of sending garbled text to Stage 3.

**Log evidence:**
```
2026-05-29T18:21:47.480Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-05-29T18:21:50.676Z [voice_flow] voice_flow[stt_begin]
```
```
2026-05-29 18:21:51 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1232ms) params={}
```
```
2026-05-29 18:21:53 INFO [jane.proxy] [jane_android] stream_message brain=OpenAI history=4 msg_len=1279 file_ctx=False
```

---

