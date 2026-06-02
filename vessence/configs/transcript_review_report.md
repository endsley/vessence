# Transcript Quality Review — 2026-06-01

Generated: 2026-06-02 01:20:08

## Issue 1 [CRITICAL]

**Turn:** 2026-06-01 01:21:58
**User said:** also, for each question please write a hint section that's helpful fo the student

**Problem:** Follow-up project instruction was escalated to Stage 3 without prior conversation history.

**Root cause:** The server sent the turn to Stage 3 with history=0 even though the user said 'also' and was continuing the prior education-project/module request. Stage 3 therefore lacked the earlier span_A.q2 context.

**Suggested fix:** Fix stream_message/session history loading for audit/web sessions so consecutive turns with the same sid include prior turns, or set a pending project-edit action after Stage 3 asks/acts so follow-ups route with context.

**Log evidence:**
```
2026-06-01 01:21:57 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1363ms) params={}
```
```
2026-06-01 01:21:58 INFO [jane.proxy] [audit-178029] stream_message brain=OpenAI history=0 msg_len=103 file_ctx=False
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-06-01 01:22:22
**User said:** you have access to my education software and I would like you to make some changes

**Problem:** Stage 3 primary LLM timed out and the fallback failures happened after the pipeline already reported completion.

**Root cause:** The turn finished at 01:22:46 with a 23.8s pipeline duration, but claude_cli_llm logged primary timeout at 01:22:40 and fallback failures at 01:23:26 and 01:23:49, indicating async/background LLM work continued after the user-facing pipeline ended.

**Suggested fix:** Make Stage 3 await or cancel fallback LLM tasks before marking the stream complete, and return an explicit failure/retry response if all configured brain providers time out.

**Log evidence:**
```
2026-06-01 01:22:40 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-01 01:22:46 INFO [jane.proxy] [audit-178029] Jane stream pipeline task finished
```
```
2026-06-01 01:23:26 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-06-01 01:23:49 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI (claude) failed (exit 1): Your organization has disabled Claude subscription access for Claude C...
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-01 15:17:52
**User said:** so I was thinking if you could add another item for the search for Facebook Marketplace

**Problem:** Stage 3 response was too slow for voice interaction.

**Root cause:** The Android voice turn was sent at 15:17:49, but Stage 3 did not finish until 15:18:59, a 68.5s end-to-end delay for a spoken request.

**Suggested fix:** For voice turns, stream an immediate acknowledgement and run code/project work asynchronously, or classify project-modification requests into a dedicated long-task handler that reports progress.

**Log evidence:**
```
2026-06-01T15:17:49.843Z [voice_flow] voice_flow[send_message] text_len=87 fromVoice=True
```
```
2026-06-01 15:17:51 INFO [jane.proxy] [jane_android] stream_message brain=OpenAI history=0 msg_len=87 file_ctx=False
```
```
2026-06-01 15:18:59 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (68481ms)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-01 15:19:21
**User said:** I would like you to add electric skateboard

**Problem:** Stage 3 response was extremely slow for a follow-up voice turn.

**Root cause:** The Android client captured the follow-up and sent it at 15:19:18, but Stage 3 finished at 15:20:58, taking 97.3s. The user interrupted/started another voice flow afterward, consistent with poor voice UX.

**Suggested fix:** Use a pending project-edit action for follow-up item additions and acknowledge immediately, then perform the longer repository edit/build work out of band.

**Log evidence:**
```
2026-06-01T15:19:18.824Z [voice_flow] voice_flow[send_message] text_len=43 fromVoice=True
```
```
2026-06-01 15:19:21 INFO [jane.proxy] [jane_android] stream_message brain=OpenAI history=2 msg_len=43 file_ctx=False
```
```
2026-06-01 15:20:58 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (97258ms)
```
```
2026-06-01T15:21:53.774Z [voice_flow] voice_flow[stop_speaking_requested]
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-06-01 15:21:59
**User said:** 

**Problem:** Client-side STT relaunch failed with no recognized speech.

**Root cause:** After the user stopped speech output, the client relaunched STT through sentence_tts, reached stt_ready, then emitted stt_error reason=no_match instead of producing a user turn.

**Suggested fix:** After stop_speaking_requested, add a short audio-settling delay and restart wake/STT cleanly; log microphone/audio focus state around relaunch to identify why no_match occurs.

**Log evidence:**
```
2026-06-01T15:21:53.774Z [voice_flow] voice_flow[stop_speaking_requested]
```
```
2026-06-01T15:21:53.794Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-06-01T15:21:53.928Z [voice_flow] voice_flow[stt_ready]
```
```
2026-06-01T15:21:59.030Z [voice_flow] voice_flow[stt_error] reason=no_match
```

---

## Issue 6 [LOW]

**Turn:** 2026-06-01 15:23:44
**User said:** well can you just give yourself these access you have root access anyways

**Problem:** Stage 1 produced an invalid class before coercing it to others.

**Root cause:** The classifier returned unknown class 'web automation', which is not in the allowed taxonomy, then mapped it to others. The final escalation was acceptable, but the classifier schema enforcement failed.

**Suggested fix:** Constrain the classifier decoder/output parser to the allowed intent enum and add a test that invalid labels are rejected before confidence/category logging.

**Log evidence:**
```
2026-06-01 15:23:43 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-01 15:23:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (837ms) params={}
```

---

## Issue 7 [LOW]

**Turn:** 2026-06-01 15:24:41
**User said:** 

**Problem:** Client relaunched STT after the final response but captured no usable speech.

**Root cause:** The client auto-launched STT via sentence_tts at 15:24:36 and reached ready state, then failed with reason=no_match. No corresponding server turn was created.

**Suggested fix:** Only auto-relaunch STT when the assistant explicitly expects a follow-up, or prompt the user with a clear listening state and suppress relaunch after terminal answers.

**Log evidence:**
```
2026-06-01T15:24:36.398Z [voice_flow] voice_flow[stt_launch]
```
```
2026-06-01T15:24:36.399Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-06-01T15:24:36.524Z [voice_flow] voice_flow[stt_ready]
```
```
2026-06-01T15:24:41.660Z [voice_flow] voice_flow[stt_error] reason=no_match
```

---

