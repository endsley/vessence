# Transcript Quality Review — 2026-04-18

Generated: 2026-04-19 01:29:08

## Issue 1 [CRITICAL]

**Turn:** 2026-04-18 10:56:43
**User said:** what time is it

**Problem:** Obvious time request was routed as a stale Stage 3 follow-up instead of going through Stage 1/Stage 2 get-time fast path.

**Root cause:** The transcript shows the turn was treated as the answer to [[AWAITING:re_sign_in_confirm]], so pending_action_resolver bypassed classification even though the new utterance was a clear standalone GET_TIME intent.

**Suggested fix:** Add a resolver pre-check for high-precision interrupt intents such as GET_TIME, WEATHER, TIMER, SMS, and CANCEL; if matched, clear or suspend the pending action and run normal Stage 1 classification.

**Log evidence:**
```
[2026-04-18 10:56:43] (jane_android) what time is it
```
```
[STAGE3 FOLLOWUP] Your previous reply ended with [[AWAITING:re_sign_in_confirm]] — the user's message above is their answer to that pending question. Continue the task.
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-18 12:10:13
**User said:** how about the air quality

**Problem:** Air-quality weather request was classified correctly but Stage 2 rejected it and escalated to slow Stage 3.

**Root cause:** Stage 1 classified WEATHER with confidence 1.00, but the weather handler gate rejected the phrase and self-corrected it into DELEGATE_OPUS, causing a 39.5s Opus turn instead of a fast handler response.

**Suggested fix:** Extend the weather handler gate and handler implementation to support air-quality queries; do not self-correct valid class-labeled utterances into DELEGATE_OPUS until a reviewer or post-check verifies the class was actually wrong.

**Log evidence:**
```
2026-04-18 12:10:11 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=38ms)
```
```
2026-04-18 12:10:11 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: gate check rejected 'how about the air quality' for class 'weather' → escalating
```
```
2026-04-18 12:10:12 INFO [jane_web.jane_v2.stage2_dispatcher] self-correct: added 'how about the air quality' to DELEGATE_OPUS (was: weather, id: DELEGATE_OPUS_auto_1776528611)
```
```
2026-04-18 12:10:53 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 39543ms (262 chars, 2 raw events)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-18 13:36:43
**User said:** how are you

**Problem:** Greeting fast path was correct but too slow for a Stage 2 handler.

**Root cause:** Stage 1 took only 52ms, while the deterministic greeting handler consumed 8587ms. The delay is inside Stage 2, not classification or Opus.

**Suggested fix:** Make greeting responses fully local and nonblocking; remove any memory, broadcast, or external calls from the greeting handler path and add a latency assertion for greetings under 500ms.

**Log evidence:**
```
2026-04-18 13:36:43 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: greeting:High  (raw=GREETING conf=1.00 margin=1.00 lat=39ms)
```
```
2026-04-18 13:36:43 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage1 greeting:High (52ms)
```
```
2026-04-18 13:36:52 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 greeting handler (8587ms)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-04-18 13:37:00
**User said:** weather question

**Problem:** Weather fast path was correct but took 7.5 seconds in Stage 2.

**Root cause:** Stage 1 classified WEATHER in 56ms, and no Stage 3 escalation occurred; the latency is proven to be inside the Stage 2 weather handler, which took 7499ms.

**Suggested fix:** Instrument the weather handler by sub-step, cache current weather reads briefly, and enforce a timeout/fallback response so Stage 2 weather does not block voice UX for multiple seconds.

**Log evidence:**
```
2026-04-18 13:37:00 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=39ms)
```
```
2026-04-18 13:37:00 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage1 weather:High (56ms)
```
```
2026-04-18 13:37:08 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (7499ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-04-18 13:47:00
**User said:** what's the weather like today

**Problem:** Weather request was hijacked by stale restart-confirmation pending action.

**Root cause:** After the user confirmed restart with 'yes please', the system restarted the standing brain but did not clear [[AWAITING:confirm_restart]]. The next unrelated weather request bypassed Stage 1 and was routed as stage3_followup.

**Suggested fix:** Clear pending_action immediately after an affirmative confirmation starts or completes the action; also add topic-change detection in pending_action_resolver so clear weather/time/timer requests cannot be consumed by unrelated confirmations.

**Log evidence:**
```
2026-04-18 13:44:52 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=confirm_restart)
```
```
2026-04-18 13:45:07 INFO [jane.standing_brain] Standing brain started: provider=claude model=claude-opus-4-6 pid=798521
```
```
2026-04-18 13:46:59 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=confirm_restart)
```
```
2026-04-18 13:47:00 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: resolver → stage3_followup (awaiting=confirm_restart)
```
```
[2026-04-18 13:47:00] (jane_android) what's the weather like today
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-18 13:50:57
**User said:** I was under the impression that stage two's handlers of various classes are identical...

**Problem:** Stage 3 follow-ups lost the original class protocol/context.

**Root cause:** Weather-related follow-up turns were escalated as synthetic class stage3_followup with class_protocol=missing:stage3_followup, so Opus did not receive the same class metadata/protocol that the original weather class had loaded.

**Suggested fix:** Persist original_class and original_class_protocol on pending_action; when resolving stage3_followup, load that original protocol instead of looking for a stage3_followup protocol.

**Log evidence:**
```
2026-04-18 13:49:25 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=confirm_weather_fix
```
```
2026-04-18 13:50:56 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=confirm_weather_fix)
```
```
2026-04-18 13:50:57 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=stage3_followup:High voice=False prompt_len=480 sid_override=True class_protocol=missing:stage3_followup
```
```
2026-04-18 13:53:20 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=stage3_followup:High voice=False prompt_len=594 sid_override=True class_protocol=missing:stage3_followup
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-04-18 13:53:21
**User said:** yeah I would like you to add the weather metadata to the Handler for stage 3...

**Problem:** Stage 3 implementation turn took almost five minutes.

**Root cause:** The follow-up was routed correctly to Stage 3, but the standing brain turn completed in 295463ms, making the voice pipeline effectively unusable for that turn.

**Suggested fix:** For code-edit or long-running implementation requests from voice, immediately acknowledge and enqueue a background job; do not block the voice response stream until Opus completes the whole task.

**Log evidence:**
```
2026-04-18 13:53:21 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=6 msg_len=594 file_ctx=False
```
```
2026-04-18 13:58:16 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 4 complete in 295463ms (1524 chars, 2 raw events)
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-04-18 14:55:26
**User said:** what is all my to-do list

**Problem:** Valid todo-list read request was rejected by Stage 2 and escalated.

**Root cause:** Stage 1 correctly classified TODO_LIST with confidence 1.00, but the todo-list gate rejected the wording and self-corrected it into DELEGATE_OPUS, adding bad training data for a valid todo query.

**Suggested fix:** Broaden todo-list gate patterns for 'what is all my to-do list', 'what's on my todo', and variants; disable automatic DELEGATE_OPUS self-correction when Stage 1 confidence is High and the utterance contains todo/list keywords.

**Log evidence:**
```
2026-04-18 14:55:24 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: todo list:High  (raw=TODO_LIST conf=1.00 margin=1.00 lat=42ms)
```
```
2026-04-18 14:55:25 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: gate check rejected 'what is all my to-do list' for class 'todo list' → escalating
```
```
2026-04-18 14:55:25 INFO [jane_web.jane_v2.stage2_dispatcher] self-correct: added 'what is all my to-do list' to DELEGATE_OPUS (was: todo list, id: DELEGATE_OPUS_auto_1776538525)
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-04-18 15:58:19
**User said:** music play request

**Problem:** Android/server client-side execution was degraded by rate limiting during a voice interaction.

**Root cause:** The same client IP was repeatedly rate-limited on image, announcements, diagnostics, playlists, and playlist detail endpoints around the music-play turn, meaning normal Android polling/tool support traffic was being throttled.

**Suggested fix:** Throttle/dedupe Android polling, cache static image requests, and exempt or separately bucket device-diagnostics and announcements from user-command API rate limits.

**Log evidence:**
```
2026-04-18 15:58:15 WARNING [jane.web] Rate limited 172.56.194.224 on /api/device-diagnostics (api)
```
```
2026-04-18 15:58:19 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: music play:High  (raw=MUSIC_PLAY conf=1.00 margin=1.00 lat=49ms)
```
```
2026-04-18 15:58:21 WARNING [jane.web] Rate limited 172.56.194.224 on /api/playlists (api)
```
```
2026-04-18 15:58:21 WARNING [jane.web] Rate limited 172.56.194.224 on /api/playlists/9ae4278925d33b2c (api)
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-04-18 17:40:55
**User said:** yes I would like you to add an item into the Urgent list

**Problem:** Todo add follow-up flow broke and escalated to Stage 3 instead of staying in the deterministic todo handler.

**Root cause:** After the todo handler set awaiting=add_category, resolver invoked the follow-up handler, but a subsequent empty/duplicate follow-up produced q='' with raw='SAME'. The handler abandoned pending state and fell through to Stage 1/Stage 3.

**Suggested fix:** Ignore empty follow-up transcripts during pending todo flows; only abandon pending state on a substantive topic-change utterance, and debounce relaunch-generated duplicate turns.

**Log evidence:**
```
2026-04-18 17:40:40 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=add_category)
```
```
2026-04-18 17:40:50 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=add_category)
```
```
2026-04-18 17:40:51 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: continuation check for 'todo list' → SAME (q='' raw='SAME')
```
```
2026-04-18 17:40:51 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```
```
2026-04-18 17:41:41 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=todo_item_text
```

---

## Issue 11 [MEDIUM]

**Turn:** 2026-04-18 18:00:47
**User said:** what time is it

**Problem:** Get-time fast path was correct but consistently too slow.

**Root cause:** GET_TIME classified correctly, but the Stage 2 get-time handler took 3496ms, then later 3019ms and 2925ms. A time response should be local and sub-second.

**Suggested fix:** Make get-time handler use only local clock/timezone data with no network, LLM, memory, or broadcast work; add a latency budget test under 300ms for GET_TIME.

**Log evidence:**
```
2026-04-18 18:00:47 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: get time:High  (raw=GET_TIME conf=1.00 margin=1.00 lat=782ms)
```
```
2026-04-18 18:00:51 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 get time handler (3496ms)
```
```
2026-04-18 18:01:20 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 get time handler (3019ms)
```
```
2026-04-18 18:04:18 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 get time handler (2925ms)
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-04-18 19:04:21
**User said:** wakeword detected, then no speech captured

**Problem:** Client listening flow launched STT, got no_match, then dropped back without a useful relaunch or user-facing recovery.

**Root cause:** Android logs show wakeword detection and stt_launch, followed by stt_error reason=no_match. There is no relaunch_launched event after that no_match sequence, matching the user's report that listening turns on and then disappears.

**Suggested fix:** On wakeword-triggered no_match, explicitly restart always-listening/wakeword mode and log the transition; optionally play a short prompt or extend the first-listen timeout before closing STT.

**Log evidence:**
```
2026-04-18T19:04:21.719Z [wakeword] Detected (score=0.9993416)
```
```
2026-04-18T19:04:21.729Z [voice_flow] voice_flow[stt_launch]
```
```
2026-04-18T19:04:28.216Z [voice_flow] voice_flow[stt_error] reason=no_match
```
```
2026-04-18T19:04:28.456Z [wakeword] Model loaded: hey_jane.onnx
```

---

## Issue 13 [LOW]

**Turn:** 2026-04-18 19:46:47
**User said:** okay sometimes you turn the listening on but then you don't listen anything and goes away

**Problem:** Stage 1 misclassified an STT/listening bug report as music playback.

**Root cause:** The classifier returned MUSIC_PLAY with confidence 1.00 for a sentence about the assistant listening state. Stage 2 gate rejected it and escalated, so the wrong handler did not execute, but classification was still incorrect.

**Suggested fix:** Add negative examples for 'listening on', 'don't listen', 'STT', and 'goes away' to keep assistant-debug utterances out of MUSIC_PLAY; add a support/debug intent or route these to DELEGATE_OPUS directly.

**Log evidence:**
```
2026-04-18 19:46:45 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: music play:High  (raw=MUSIC_PLAY conf=1.00 margin=1.00 lat=276ms)
```
```
2026-04-18 19:46:46 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: gate check rejected "okay sometimes you turn the listening on but then you don't " for class 'music play' → escalating
```
```
2026-04-18 19:46:46 INFO [jane_web.jane_v2.stage2_dispatcher] self-correct: added "okay sometimes you turn the listening on but then you don't " to DELEGATE_OPUS (was: music play, id: DELEGATE_OPUS_auto_1776556006)
```

---

## Issue 14 [MEDIUM]

**Turn:** 2026-04-18 21:18:57
**User said:** device diagnostics upload

**Problem:** Android diagnostic execution blocked on database locks for nearly two minutes.

**Root cause:** POST /api/device-diagnostics requests failed after 111-113 seconds with 'database is locked', indicating diagnostic writes can block long enough to starve or fail client telemetry.

**Suggested fix:** Move diagnostics ingestion to a queue or WAL-backed writer with short busy_timeout; return 202 quickly instead of holding HTTP requests while SQLite is locked.

**Log evidence:**
```
2026-04-18 21:18:57 ERROR [jane.web] Unhandled error in POST /api/device-diagnostics after 111544ms: database is locked
```
```
2026-04-18 21:18:59 ERROR [jane.web] Unhandled error in POST /api/device-diagnostics after 113649ms: database is locked
```
```
2026-04-18 21:18:59 ERROR [jane.web] Unhandled error in POST /api/device-diagnostics after 113671ms: database is locked
```

---

## Issue 15 [CRITICAL]

**Turn:** 2026-04-18 21:30:43
**User said:** I want to add an item to the clinic and the item is to create a clinic Gmail account

**Problem:** Todo handler failed to parse category and item from a complete add-item request.

**Root cause:** Stage 1 correctly classified TODO_LIST, but Stage 2 took 5743ms and set a category follow-up despite the utterance already containing category 'clinic' and item text. The subsequent continuation saw '4 categories...' as CHANGED, abandoned the handler, and escalated to Stage 3 for 64s.

**Suggested fix:** Update todo parser to extract both category and item from 'add an item to/into <category> and the item is <text>'; suppress STT relaunch while Jane is reading category choices so the assistant's own TTS cannot become the next user turn.

**Log evidence:**
```
2026-04-18 21:30:11 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: todo list:High  (raw=TODO_LIST conf=1.00 margin=1.00 lat=57ms)
```
```
2026-04-18 21:30:17 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 todo list handler (5743ms)
```
```
2026-04-18 21:30:34 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-18 21:30:34 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: continuation check for 'todo list' → CHANGED (q='4 categories: the urgent stuff, students, home, an' raw='CHANGED')
```
```
2026-04-18 21:31:47 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 64002ms (134 chars, 2 raw events)
```

---

## Issue 16 [MEDIUM]

**Turn:** 2026-04-18 21:52:45
**User said:** what's on my todo

**Problem:** Valid todo-list read request was again rejected by the Stage 2 gate.

**Root cause:** Stage 1 classified TODO_LIST with confidence 1.00, but the gate rejected the short natural phrasing and self-corrected it into DELEGATE_OPUS, forcing Stage 3.

**Suggested fix:** Treat 'what's on my todo' as a canonical todo-list read phrase in the gate; remove the generated DELEGATE_OPUS self-correction entry for this utterance.

**Log evidence:**
```
2026-04-18 21:52:43 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: todo list:High  (raw=TODO_LIST conf=1.00 margin=1.00 lat=117ms)
```
```
2026-04-18 21:52:43 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: gate check rejected "what's on my todo" for class 'todo list' → escalating
```
```
2026-04-18 21:52:44 INFO [jane_web.jane_v2.stage2_dispatcher] self-correct: added "what's on my todo" to DELEGATE_OPUS (was: todo list, id: DELEGATE_OPUS_auto_1776563563)
```

---

## Issue 17 [MEDIUM]

**Turn:** 2026-04-18 22:21:46
**User said:** why what's on my to-do list

**Problem:** Another valid todo-list query was rejected by Stage 2 and mislabeled for delegation.

**Root cause:** Stage 1 correctly returned TODO_LIST, but Stage 2 gate rejected the utterance because of the leading 'why', then self-corrected it into DELEGATE_OPUS.

**Suggested fix:** Normalize filler/false-start words such as 'why', 'wait', and 'so' before todo gate checks; prevent self-correct from adding high-confidence TODO_LIST turns to DELEGATE_OPUS.

**Log evidence:**
```
2026-04-18 22:21:40 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: todo list:High  (raw=TODO_LIST conf=1.00 margin=1.00 lat=39ms)
```
```
2026-04-18 22:21:41 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: gate check rejected "why what's on my to-do list" for class 'todo list' → escalating
```
```
2026-04-18 22:21:45 INFO [jane_web.jane_v2.stage2_dispatcher] self-correct: added "why what's on my to-do list" to DELEGATE_OPUS (was: todo list, id: DELEGATE_OPUS_auto_1776565301)
```

---

## Issue 18 [MEDIUM]

**Turn:** 2026-04-18 22:42:02
**User said:** can you add an item into the clinic

**Problem:** Todo add request was misclassified as others and sent to Stage 3.

**Root cause:** The utterance clearly requests adding a todo item to category 'clinic', but Stage 1 returned DELEGATE_OPUS/others Low, so the deterministic todo handler never got a chance to ask for the item text.

**Suggested fix:** Add TODO_LIST classifier examples and a rule-based override for 'add an item into/to <category>'; route to todo handler with awaiting=item_text when item text is missing.

**Log evidence:**
```
[2026-04-18 22:42:02] (jane_android) can you add an item into the clinic
```
```
2026-04-18 22:42:00 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.60 margin=0.20 dist=0.294 lat=86ms)
```
```
2026-04-18 22:42:01 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=168 sid_override=True class_protocol=n/a
```
```
2026-04-18 22:42:52 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=clinic_todo_item
```

---

## Issue 19 [MEDIUM]

**Turn:** 2026-04-18 23:10:49
**User said:** so all together we have three phases for this project

**Problem:** A project-context correction was swallowed by unclear_prompt short-circuit on the previous related turn.

**Root cause:** The classifier produced FORCE_STAGE3/others for the phase-count discussion, but the pipeline fired unclear_prompt short-circuit at 23:10:39. That prevented Stage 3 from handling a context-dependent correction/clarification in the web automation project thread.

**Suggested fix:** Disable unclear_prompt short-circuit when recent history contains an active project discussion or when raw=FORCE_STAGE3; send the turn to Stage 3 with recent history so corrections can update the answer.

**Log evidence:**
```
2026-04-18 23:10:39 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=FORCE_STAGE3 conf=1.00 margin=1.00 dist=0.261 lat=29ms)
```
```
2026-04-18 23:10:39 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: unclear_prompt short-circuit fired
```
```
2026-04-18 23:10:48 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=FORCE_STAGE3 conf=0.80 margin=0.60 dist=0.235 lat=24ms)
```
```
2026-04-18 23:10:49 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=183 sid_override=True class_protocol=n/a
```

---

## Issue 20 [CRITICAL]

**Turn:** 2026-04-18 23:41:50
**User said:** web automation skill run

**Problem:** Web automation tool execution crashed because Playwright browser binary was missing.

**Root cause:** The skill attempted to launch Chromium headless_shell at a Playwright cache path that does not exist.

**Suggested fix:** Install the required Playwright browser during deployment with the same user/cache path used by jane-web, or configure PLAYWRIGHT_BROWSERS_PATH to a managed shared location and add a startup health check.

**Log evidence:**
```
2026-04-18 23:41:50 ERROR [agent_skills.web_automation.skill] skill.run_task crashed: BrowserType.launch: Executable doesn't exist at /home/chieh/.cache/ms-playwright/chromium_headless_shell-1155/chrome-linux/headless_shell
```

---

