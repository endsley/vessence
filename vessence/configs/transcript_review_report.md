# Transcript Quality Review — 2026-04-22

Generated: 2026-04-23 01:34:29

## Issue 1 [CRITICAL]

**Turn:** 2026-04-22 10:46:44
**User said:** huh why you crashing some other times

**Problem:** Live session endpoint was repeatedly crashing.

**Root cause:** GET /api/jane/live raised a TypeError because end_session() was called without the required session_id argument.

**Suggested fix:** Fix the /api/jane/live cleanup path to pass session_id into end_session(), or make end_session accept/derive the active session safely.

**Log evidence:**
```
2026-04-22 17:05:30 ERROR [jane.web] Unhandled error in GET /api/jane/live after 47ms: end_session() missing 1 required positional argument: 'session_id'
```
```
2026-04-22 17:06:43 ERROR [jane.web] Unhandled error in GET /api/jane/live after 42ms: end_session() missing 1 required positional argument: 'session_id'
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-22 11:57:01
**User said:** how about for the clinic

**Problem:** Todo list response repeated the same clinic item twice.

**Root cause:** Stage 2 returned duplicate clinic todos even though later summary recognized only 5 unique clinic items, indicating the todo handler or Google Doc cache presentation layer did not normalize/dedupe items before speaking.

**Suggested fix:** Deduplicate todo items in the Google Doc sync or Stage 2 todo list formatter using normalized text keys before counting and rendering category items.

**Log evidence:**
```
jane: 6 items for the clinic. Curtain rods at kathia’s clinic; The wooden block for the door at the clinic; Create a clinic Gmail account; Put mirrors up; Add texting capability to the laptop; and finally, Add texting capability to the laptop.
```
```
2026-04-22 11:58:49 ... Clinic todos contain 5 unique items (Curtain rods, Wooden block for door, Create Gmail
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-22 17:14:55
**User said:** can you sing deeply and tell me a joke

**Problem:** Stage 3 gave an unhelpful clarification response instead of handling the joke request or explaining the singing limitation.

**Root cause:** Stage 1 correctly sent the ambiguous/non-handler request to Stage 3 as others:Low, but Opus replied 'Sorry, could you say that again?' despite enough intent to at least tell a joke.

**Suggested fix:** Add Stage 3 instruction for mixed entertainment/audio-modulation requests: comply with text-safe parts like jokes and briefly state unavailable voice effects instead of asking for repetition.

**Log evidence:**
```
2026-04-22 17:14:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (735ms)
```
```
2026-04-22 17:14:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=698 sid_override=True class_protocol=n/a
```
```
user: can you sing deeply and tell me a joke
```
```
jane: Sorry, could you say that again?
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-04-22 17:16:29
**User said:** how many events do I have next week

**Problem:** Calendar query was misclassified as others and routed to slow Stage 3.

**Root cause:** The classifier emitted an unsupported class label 'force stage3', which the wrapper mapped to others instead of read calendar.

**Suggested fix:** Constrain classifier outputs to the allowed enum and add a post-processor rule mapping calendar-count/date-range questions to read_calendar before falling back to others.

**Log evidence:**
```
2026-04-22 17:16:29 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-04-22 17:16:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (780ms)
```
```
2026-04-22 17:16:29 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1251 sid_override=True class_protocol=n/a
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-04-22 17:16:30
**User said:** how many events do I have next week

**Problem:** Stage 3 calendar answer was extremely slow.

**Root cause:** Because the read-calendar request was misrouted to Opus, the turn took 384 seconds end-to-end instead of using the fast Stage 2 calendar handler.

**Suggested fix:** Prevent read_calendar turns from escalating on classifier uncertainty when the utterance contains calendar/date-range event-count language; use Stage 2 calendar handler whenever server calendar data can be fetched.

**Log evidence:**
```
2026-04-22 17:16:30 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=2 msg_len=1251 file_ctx=False
```
```
2026-04-22 17:22:54 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 2 complete in 384136ms (1345 chars, 2 raw events)
```
```
2026-04-22 17:22:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (384290ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-22 17:27:02
**User said:** how many events do I have next week

**Problem:** Calendar follow-up was again misclassified as others and escalated to Stage 3.

**Root cause:** The classifier again returned unsupported 'force stage3', causing a fallback to others despite the active calendar context.

**Suggested fix:** Teach the pending/action context and classifier repair layer that event-count follow-ups after calendar turns remain read_calendar unless the user clearly changes topic.

**Log evidence:**
```
2026-04-22 17:27:02 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-04-22 17:27:02 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (824ms)
```
```
2026-04-22 17:27:03 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1834 sid_override=True class_protocol=n/a
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-04-22 17:29:20
**User said:** how many events do I have next week

**Problem:** Calendar follow-up continued to route through Stage 3 instead of the deterministic calendar handler.

**Root cause:** Stage 1 classified the turn as others:Low even though the transcript shows an active calendar query sequence.

**Suggested fix:** Add conversation-aware classification repair for calendar follow-ups and prefer read_calendar when recent assistant turns are calendar summaries.

**Log evidence:**
```
2026-04-22 17:29:20 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (803ms)
```
```
2026-04-22 17:29:21 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=2382 sid_override=True class_protocol=n/a
```
```
user: how many events do I have next week
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-04-22 17:31:05
**User said:** Class Protocol: Read Calendar

**Problem:** Protocol metadata was misclassified as send message.

**Root cause:** Stage 1 treated injected class-protocol text as a user SMS intent, then the send-message handler returned an invalid shape and escalated to Stage 3.

**Suggested fix:** Filter protocol/summary metadata out of user-turn classification, or tag it as system context so Stage 1 never sees it as user intent.

**Log evidence:**
```
2026-04-22 17:31:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (820ms)
```
```
2026-04-22 17:31:06 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-04-22 17:31:06 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=send message:Very High voice=False prompt_len=5357 sid_override=True class_protocol=loaded:send_message
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-04-22 17:49:07
**User said:** Class Protocol: Read Calendar

**Problem:** Pending clinic follow-up leaked across topic changes and polluted later routing.

**Root cause:** The resolver repeatedly logged followup → clinic schedules info awaiting=another_patient immediately before unrelated calendar/protocol turns, showing stale clinic pending_action was not cleared reliably on topic change.

**Suggested fix:** Clear pending Stage 2 follow-ups on high-confidence unrelated intents and on non-user protocol metadata; add expiry/turn-count limits for clinic follow-up states.

**Log evidence:**
```
2026-04-22 17:48:58 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=another_patient)
```
```
2026-04-22 17:48:58 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:High (795ms)
```
```
2026-04-22 17:49:07 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=another_patient)
```
```
2026-04-22 17:49:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1287ms)
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-04-22 18:12:34
**User said:** what's the weather like tomorrow

**Problem:** Weather request was misclassified as others and sent to Stage 3.

**Root cause:** Stage 1 returned others:Low for a direct weather query, so the deterministic weather handler was bypassed.

**Suggested fix:** Add a high-priority regex/keyword guard for weather utterances before model classification fallback.

**Log evidence:**
```
2026-04-22 18:12:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (849ms)
```
```
2026-04-22 18:12:35 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1054 sid_override=True class_protocol=n/a
```
```
user: what's the weather l
```

---

## Issue 11 [CRITICAL]

**Turn:** 2026-04-22 18:12:35
**User said:** what's the weather like tomorrow

**Problem:** Stage 3 answered stale calendar-protocol context instead of the weather request.

**Root cause:** Because the weather request was routed as others with no weather class protocol, Opus focused on prior read_calendar protocol metadata and complained that no CALENDAR DATA block was included.

**Suggested fix:** Prevent protocol metadata from being injected as conversational user content, and route direct weather queries to the Stage 2 weather handler.

**Log evidence:**
```
2026-04-22 18:12:35 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1054 sid_override=True class_protocol=n/a
```
```
I understand the read_calendar protocol. The server fetches your Google Calendar events and I summarize them for you.
```
```
However, no [CALENDAR DATA] block was included in your message. Would you like me to check your calendar for a specific date (today, tomorrow, this week)?
```
```
user: what's the weather l
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-04-22 18:15:18
**User said:** what's the weather like tomorrow

**Problem:** Weather request was again misclassified as others and escalated.

**Root cause:** Stage 1 still returned others:Low for a direct weather utterance, repeating the same weather classifier failure.

**Suggested fix:** Add deterministic weather intent preclassification for phrases like 'what's the weather like tomorrow' and ensure pending protocol metadata cannot override it.

**Log evidence:**
```
2026-04-22 18:15:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1241ms)
```
```
2026-04-22 18:15:19 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1095 sid_override=True class_protocol=n/a
```

---

## Issue 13 [MEDIUM]

**Turn:** 2026-04-22 18:16:10
**User said:** what's the weather like tomorrow

**Problem:** Weather request continued to bypass the Stage 2 weather handler.

**Root cause:** Stage 1 classified the direct weather query as others:Low, causing unnecessary Stage 3 use.

**Suggested fix:** Instrument classifier examples and add tests for exact weather phrasing captured in the transcript.

**Log evidence:**
```
2026-04-22 18:16:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1287ms)
```
```
2026-04-22 18:16:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1448 sid_override=True class_protocol=n/a
```
```
user: what's the weather like tomorrow
```

---

## Issue 14 [MEDIUM]

**Turn:** 2026-04-22 19:07:03
**User said:** [TOOL_RESULT:{"tool":"timer.set"...}] can you set a timer for 5 minutes

**Problem:** Server processed a client TOOL_RESULT as part of a new user timer request.

**Root cause:** Android/client transcript sent the previous timer.set tool result inline with the user's new utterance; Stage 1 and the timer parser consumed the combined text as if it were user speech.

**Suggested fix:** Strip or separately route TOOL_RESULT blocks before Stage 1 classification and prevent client tool results from being concatenated into the next user message.

**Log evidence:**
```
user: [TOOL_RESULT:{"tool":"timer.set","call_id":"292da6ff-bff9-490a-b046-aeaccbfcdc10","status":"completed","message":"timer set for 540000ms"}] can you set a timer for 5 minutes
```
```
2026-04-22 19:07:03 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 timer:Very High (823ms)
```
```
2026-04-22 19:07:03 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=300000 from prompt='[TOOL_RESULT:{"tool":"timer.set","call_id":"292da6ff-bff9-490a-b046-aeaccbfcdc10","status":"completed","message":"timer '
```

---

## Issue 15 [MEDIUM]

**Turn:** 2026-04-22 20:07:25
**User said:** [TOOL_RESULT:{"tool":"timer.set"...}]

**Problem:** Timer handler asked for duration after receiving only/mostly a tool result payload.

**Root cause:** The timer parser saw a TOOL_RESULT message, parsed duration_ms=0, and treated it as a timer intent with missing duration instead of ignoring tool-result metadata.

**Suggested fix:** Drop TOOL_RESULT blocks before timer parsing; if a message contains only tool result metadata, do not run Stage 1/Stage 2 user-intent handling.

**Log evidence:**
```
2026-04-22 20:07:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 timer:High (879ms)
```
```
2026-04-22 20:07:25 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=0 from prompt='[TOOL_RESULT:{"tool":"timer.set","call_id":"4b6feb14-7d52-4c4c-89a3-f38ce3d9376a","status":"completed","message":"timer '
```
```
2026-04-22 20:07:25 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: timer intent with no duration → ask
```

---

## Issue 16 [CRITICAL]

**Turn:** 2026-04-22 21:29:44
**User said:** [TOOL_RESULT:{"tool":"timer.set"...}] can you set a timer for 5 minutes

**Problem:** Timer request was hijacked by stale read-calendar pending action.

**Root cause:** The resolver routed the turn to read_calendar awaiting=event_detail before Stage 1, so the actual timer request was initially processed through the wrong pending flow and only escalated after the read_calendar handler returned invalid shape.

**Suggested fix:** Teach pending_action_resolver to detect high-precision interrupts like timer requests and clear unrelated pending actions before handler dispatch; also strip TOOL_RESULT metadata before resolver matching.

**Log evidence:**
```
2026-04-22 21:29:44 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → read calendar (awaiting=event_detail)
```
```
2026-04-22 21:29:44 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (807ms)
```
```
2026-04-22 21:29:45 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'read calendar' returned invalid shape → Stage 3
```
```
user: [TOOL_RESULT:{"tool":"timer.set","call_id":"292da6ff-bff9-490a-b046-aeaccbfcdc10","status":"completed","message":"timer set for 540000ms"}] can you set a timer for 5 minutes
```

---

## Issue 17 [CRITICAL]

**Turn:** 2026-04-22 21:31:00
**User said:** okay what is on my to do list

**Problem:** Todo request was misclassified as clinic schedules info.

**Root cause:** A stale read_calendar pending action was logged, then Stage 1 classified the todo-list query as clinic schedules info:High and invoked the clinic schedule handler.

**Suggested fix:** Add lexical guardrails for todo-list phrases and clear unrelated pending actions when the user asks 'what is on my to do list'.

**Log evidence:**
```
2026-04-22 21:31:00 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → read calendar (awaiting=event_detail)
```
```
2026-04-22 21:31:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:High (832ms)
```
```
2026-04-22 21:31:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 clinic schedules info handler (1ms)
```
```
user: okay what is on my to do list
```

---

## Issue 18 [CRITICAL]

**Turn:** 2026-04-22 21:32:10
**User said:** okay what is on my to do list

**Problem:** Stale clinic pending action caused a todo-list request to receive a safe deflection.

**Root cause:** The resolver forced the todo request into clinic schedules info awaiting=names_for_day_confirm; the clinic handler returned an invalid shape and the no_stage3 class produced a deflection instead of answering the todo query.

**Suggested fix:** For STAGE2_FOLLOWUP states, run high-precision interrupt detection before routing; include todo-list intents in the interrupt list and clear clinic pending state.

**Log evidence:**
```
2026-04-22 21:32:10 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-22 21:32:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (831ms)
```
```
2026-04-22 21:32:11 WARNING [jane_web.jane_v3.pipeline] jane_v3: no_stage3 class 'clinic schedules info' — handler returned invalid shape, returning safe deflection
```
```
2026-04-22 21:32:11 INFO [jane.proxy] [jane_android] Persistence worker started stage=stage2 cls=clinic schedules info user_chars=30 assistant_chars=47
```

---

## Issue 19 [MEDIUM]

**Turn:** 2026-04-22 21:34:16
**User said:** what's the weather like tomorrow

**Problem:** Weather request was misclassified as others while a todo category follow-up was pending.

**Root cause:** The resolver logged a pending todo-list category follow-up, but did not clear it cleanly for the weather interrupt; Stage 1 then returned others:Low instead of weather.

**Suggested fix:** Extend high-precision interrupt detection to weather utterances during todo follow-up states and force weather classification when matched.

**Log evidence:**
```
2026-04-22 21:34:16 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-22 21:34:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1325ms)
```
```
2026-04-22 21:34:18 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=641 sid_override=True class_protocol=n/a
```
```
user: what's the weather like tomorrow
```

---

## Issue 20 [MEDIUM]

**Turn:** 2026-04-22 22:23:04
**User said:** what's the weather like tomorrow

**Problem:** After speaking the weather response, STT relaunch did not reach ready/result and wakeword models repeatedly reloaded.

**Root cause:** Android logged stop_speaking_requested, relaunch_launched, and stt_launch, but no following stt_ready/stt_result; server also logged repeated Init session failed shortly after.

**Suggested fix:** Audit Android sentence_tts relaunch path and server init-session failure handling; ensure STT relaunch errors are surfaced and always-listening is restored after failed session init.

**Log evidence:**
```
2026-04-22T22:23:04.854Z [voice_flow] voice_flow[stop_speaking_requested]
```
```
2026-04-22T22:23:04.862Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-04-22T22:23:04.862Z [voice_flow] voice_flow[stt_launch]
```
```
2026-04-22 22:23:10 ERROR [jane.web] Init session failed
```
```
2026-04-22 22:23:33 ERROR [jane.web] Init session failed
```
```
2026-04-22 22:23:45 ERROR [jane.web] Init session failed
```

---

## Issue 21 [MEDIUM]

**Turn:** 2026-04-22 23:44:16
**User said:** briefing media load

**Problem:** Client was rate limited while loading many briefing image/audio assets.

**Root cause:** The server rate limiter blocked a burst of /api/briefing/image and /api/briefing/audio requests from the Android client IP, likely degrading briefing playback/media rendering.

**Suggested fix:** Batch or throttle briefing asset requests on Android, or adjust server rate-limit buckets for authenticated briefing media endpoints.

**Log evidence:**
```
2026-04-22 23:44:16 WARNING [jane.web] Rate limited 172.56.197.171 on /api/briefing/image/b095bf2e793f (api)
```
```
2026-04-22 23:44:16 WARNING [jane.web] Rate limited 172.56.197.171 on /api/briefing/audio/b095bf2e793f/brief (api)
```
```
2026-04-22 23:44:17 WARNING [jane.web] Rate limited 172.56.197.171 on /api/jane/announcements (api)
```

---

