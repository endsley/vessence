# Transcript Quality Review — 2026-04-20

Generated: 2026-04-21 01:28:37

## Issue 1 [CRITICAL]

**Turn:** 2026-04-20 08:47:53
**User said:** yes send it

**Problem:** SMS confirmation attempted to send with no open draft.

**Root cause:** The prior SMS request should have created a contacts.sms_draft and pending confirmation, but the later client tool result shows contacts.sms_send had no draft to send.

**Suggested fix:** Make SMS confirmation state authoritative: first turn must emit contacts.sms_draft with a stable draft_id, pending_action_resolver must route 'yes send it' to sms_send for that draft_id, and sms_send should never be emitted without an existing draft.

**Log evidence:**
```
[2026-04-20 08:47:34] (jane_android) can you ask Lee what time she's going to be there today
```
```
[2026-04-20 08:47:53] (jane_android) yes send it
```
```
[2026-04-20 09:06:03] (jane_android) [TOOL_RESULT:{"tool":"contacts.sms_send","call_id":"400a4d96-f84f-4670-ad5a-989157d22aa5","status":"failed","message":"no open draft to send"}]
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-20 15:32:08
**User said:** can you tell my wife that I took out daughter back home

**Problem:** Direct SMS request missed the Stage 2 send-message fast path.

**Root cause:** Stage 1 classified a clear 'tell my wife' message as others:Low and escalated to Stage 3 before a later send-message handler invocation appeared.

**Suggested fix:** Add classifier examples and deterministic pre-rules for 'tell/contact my wife/husband/spouse' as send message, including family aliases.

**Log evidence:**
```
2026-04-20 15:32:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (919ms)
```
```
2026-04-20 15:32:07 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=143 sid_override=True class_protocol=n/a
```
```
2026-04-20 15:32:51 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (839ms)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-20 18:34:16
**User said:** how many patients do I have today

**Problem:** Clinic schedule request was routed to Stage 3 instead of the clinic schedule handler.

**Root cause:** Qwen returned '[clinic schedules info]' with brackets; the classifier treated it as an unknown class and normalized to others:Low.

**Suggested fix:** Canonicalize classifier labels by stripping brackets, underscores, and case/spacing variants before validation.

**Log evidence:**
```
2026-04-20 18:34:15 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class '[clinic schedules info]' -> others
```
```
2026-04-20 18:34:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (849ms)
```
```
2026-04-20 18:34:15 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=125 sid_override=True class_protocol=n/a
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-04-20 19:08:00
**User said:** what does her schedule look like this week

**Problem:** Clinic-style schedule query was classified as read calendar, which has no Stage 2 handler.

**Root cause:** Stage 1 selected read calendar:Very High, then the pipeline escalated because read calendar has no handler.

**Suggested fix:** Route provider/patient schedule phrasing in clinic test sessions to clinic schedules info, or implement a read calendar handler instead of always escalating.

**Log evidence:**
```
2026-04-20 19:07:59 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (863ms)
```
```
2026-04-20 19:07:59 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'read calendar' has no handler -> Stage 3
```
```
2026-04-20 19:08:00 INFO [jane.proxy] [c6cf9268b21b] send_message (sync) brain=Claude history=0 msg_len=42 file_ctx=False
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-04-20 19:08:54
**User said:** how busy is she on Wednesday

**Problem:** Clinic schedule follow-up was over-delegated to Stage 3.

**Root cause:** Stage 1 classified the pronoun-based schedule question as delegate opus:Very High, and that class has no handler.

**Suggested fix:** Teach the classifier and pending resolver that 'how busy is she on <day>' after clinic context maps to clinic schedules info.

**Log evidence:**
```
2026-04-20 19:08:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (751ms)
```
```
2026-04-20 19:08:53 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'delegate opus' has no handler -> Stage 3
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-20 19:10:02
**User said:** is she working on Monday

**Problem:** Clinic schedule availability question was over-delegated to Stage 3.

**Root cause:** Stage 1 classified 'is she working on Monday' as delegate opus:Very High instead of clinic schedules info.

**Suggested fix:** Add clinic availability examples for 'is she working', 'is <provider> in', and pronoun follow-ups.

**Log evidence:**
```
2026-04-20 19:10:02 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (774ms)
```
```
2026-04-20 19:10:02 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'delegate opus' has no handler -> Stage 3
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-04-20 19:11:12
**User said:** who's coming in tomorrow

**Problem:** Patient schedule query was classified as read calendar and escalated.

**Root cause:** Stage 1 did not map 'who's coming in' to clinic schedules info; read calendar has no handler.

**Suggested fix:** Add clinic schedule examples for 'who is coming in', 'patients tomorrow', and 'appointments tomorrow'.

**Log evidence:**
```
2026-04-20 19:11:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (844ms)
```
```
2026-04-20 19:11:11 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'read calendar' has no handler -> Stage 3
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-04-20 19:18:02
**User said:** how about tomorrow

**Problem:** Relative-date clinic follow-up bypassed the fast path and took about 3 minutes in Stage 3.

**Root cause:** No pending clinic schedule context was resolved; Stage 1 classified the follow-up as delegate opus and Stage 3 ran for 180585ms.

**Suggested fix:** Have the clinic schedule handler set pending context for relative follow-ups, and make pending_action_resolver catch 'how about tomorrow/next week/Wednesday'.

**Log evidence:**
```
2026-04-20 19:18:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (820ms)
```
```
2026-04-20 19:18:02 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=delegate opus:Very High voice=False prompt_len=1411 sid_override=True class_protocol=loaded:delegate_opus
```
```
2026-04-20 19:21:02 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (180585ms)
```

---

## Issue 9 [MEDIUM]

**Turn:** 2026-04-20 19:24:33
**User said:** can you tell me about the clinic schedule on Wednesday

**Problem:** Explicit clinic schedule request was classified as read calendar.

**Root cause:** Despite the words 'clinic schedule', Stage 1 chose read calendar:Very High; no read calendar handler exists, so the turn escalated.

**Suggested fix:** Prioritize exact 'clinic schedule' lexical matches to clinic schedules info before model classification.

**Log evidence:**
```
2026-04-20 19:24:33 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (883ms)
```
```
2026-04-20 19:24:33 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'read calendar' has no handler -> Stage 3
```

---

## Issue 10 [CRITICAL]

**Turn:** 2026-04-20 19:31:49
**User said:** casual look like tomorrow

**Problem:** The user-facing request produced no completed answer because the stream was cancelled after client disconnect.

**Root cause:** The transcript appears to be an STT error for a schedule question, Stage 1 classified it as others:Low, and the brain execution was cancelled after 2835ms due to client disconnect or timeout.

**Suggested fix:** Do not cancel server-side brain work immediately on transient Android stream disconnect; cache the result for reconnect, and add STT correction for 'casual' -> 'schedule' in schedule contexts.

**Log evidence:**
```
2026-04-20 19:31:47 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (833ms)
```
```
2026-04-20 19:31:51 INFO [jane.proxy] [jane_android] Client disconnected - waiting for adapter task to finish (brain still working)
```
```
2026-04-20 19:31:52 WARNING [jane.proxy] [jane_android] Brain execution cancelled (stream) after 2835ms - likely client disconnect or timeout.
```

---

## Issue 11 [LOW]

**Turn:** 2026-04-20 19:32:09
**User said:** what does my schedule look like tomorrow

**Problem:** Classifier alias was rejected, losing the intended read-calendar protocol.

**Root cause:** Qwen returned 'read_calendar' with an underscore; the classifier treated it as unknown and converted it to others:Low.

**Suggested fix:** Normalize underscores to spaces when validating classifier labels.

**Log evidence:**
```
2026-04-20 19:32:08 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'read_calendar' -> others
```
```
2026-04-20 19:32:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (890ms)
```
```
2026-04-20 19:32:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=141 sid_override=True class_protocol=n/a
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-04-20 19:32:33
**User said:** what is my clinic schedule look like tomorrow

**Problem:** Explicit clinic schedule request was sent to read calendar and escalated.

**Root cause:** Stage 1 chose read calendar:Very High even though the request said 'clinic schedule'; read calendar has no Stage 2 handler.

**Suggested fix:** Add a high-priority rule mapping 'my clinic schedule' to clinic schedules info.

**Log evidence:**
```
2026-04-20 19:32:32 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (1007ms)
```
```
2026-04-20 19:32:32 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'read calendar' has no handler -> Stage 3
```

---

## Issue 13 [MEDIUM]

**Turn:** 2026-04-20 20:53:52
**User said:** any cancellations

**Problem:** Clinic cancellation follow-up did not use prior clinic schedule context.

**Root cause:** After a clinic schedules info Stage 2 turn, the follow-up 'any cancellations' was classified as others:Low and escalated to Stage 3 for 41442ms.

**Suggested fix:** Set pending clinic context after schedule responses and route cancellation follow-ups to the clinic schedule handler.

**Log evidence:**
```
2026-04-20 20:53:41 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:High (814ms)
```
```
2026-04-20 20:53:51 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (681ms)
```
```
2026-04-20 20:54:33 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (41442ms)
```

---

## Issue 14 [CRITICAL]

**Turn:** 2026-04-20 21:13:17
**User said:** for the first patient I would like to know more details about the patient

**Problem:** Patient-detail follow-up lost the clinic schedule context.

**Root cause:** The prior clinic schedule answer came from Stage 2, but this follow-up went to Stage 3 with history=0, so Stage 3 had no prior patient list to resolve 'the first patient'.

**Suggested fix:** Persist Stage 2 clinic schedule outputs into short-term conversational state and have pending_action_resolver route ordinal follow-ups like 'first patient' to the clinic detail handler.

**Log evidence:**
```
2026-04-20 21:12:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 clinic schedules info handler (1ms)
```
```
2026-04-20 21:13:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (894ms)
```
```
2026-04-20 21:13:17 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=0 msg_len=174 file_ctx=False
```
```
2026-04-20 21:13:43 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 25249ms (33 chars, 5 raw events)
```

---

## Issue 15 [CRITICAL]

**Turn:** 2026-04-20 21:28:47
**User said:** can you delete it for me

**Problem:** Contextual delete request was misclassified as send email and the handler returned an invalid shape.

**Root cause:** After reading messages and the user saying the item was junk, Stage 1 chose send email:Very High for 'delete it'; the send email handler could not produce a valid response and escalated.

**Suggested fix:** Add delete-message/delete-email contextual intents and make pending_action_resolver bind 'delete it' to the last read item instead of using send email.

**Log evidence:**
```
2026-04-20 21:28:04 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read messages:Very High (1357ms)
```
```
2026-04-20 21:28:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (885ms)
```
```
2026-04-20 21:28:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send email:Very High (820ms)
```
```
2026-04-20 21:28:46 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send email' returned invalid shape -> Stage 3
```

---

## Issue 16 [MEDIUM]

**Turn:** 2026-04-20 21:30:10
**User said:** no I would like to know which patients canceled

**Problem:** Clinic cancellation query was classified as others instead of clinic schedules info.

**Root cause:** The classifier did not recognize 'which patients canceled' as a clinic schedule query and escalated to Stage 3.

**Suggested fix:** Add cancellation-specific clinic examples and a deterministic rule for 'patients canceled/cancelled'.

**Log evidence:**
```
2026-04-20 21:30:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (790ms)
```
```
2026-04-20 21:30:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=148 sid_override=True class_protocol=n/a
```

---

## Issue 17 [MEDIUM]

**Turn:** 2026-04-20 21:31:37
**User said:** no I would like to know more details about the first patient

**Problem:** Repeated ordinal patient-detail follow-up was not routed to the clinic handler.

**Root cause:** Stage 1 again classified a 'first patient' detail request as others:Low, relying on Stage 3 and conversation history instead of deterministic clinic context.

**Suggested fix:** Keep the last clinic schedule result in structured session state and resolve ordinal patient references before Stage 1.

**Log evidence:**
```
2026-04-20 21:31:14 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 clinic schedules info handler (1ms)
```
```
2026-04-20 21:31:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (858ms)
```
```
2026-04-20 21:31:37 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=161 sid_override=True class_protocol=n/a
```

---

## Issue 18 [MEDIUM]

**Turn:** 2026-04-20 21:40:06
**User said:** I'm talking about the first patient on Wednesday

**Problem:** Disambiguated clinic patient-detail request still missed the clinic fast path.

**Root cause:** Even with 'first patient on Wednesday', Stage 1 returned others:Low and escalated; the clinic handler never received the structured date plus ordinal request.

**Suggested fix:** Extend clinic schedules info intent coverage to ordinal patient details with explicit dates, and add a Stage 2 detail lookup path.

**Log evidence:**
```
2026-04-20 21:40:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (853ms)
```
```
2026-04-20 21:40:06 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=149 sid_override=True class_protocol=n/a
```

---

## Fixes Applied (2026-04-21)

### `intent_classifier/v3/classifier.py` — deterministic clinic fast path

Added `_clinic_fast_path()` that short-circuits qwen for unambiguous
clinic-schedule phrasings. When the prompt matches patterns like
"clinic schedule", "how many patients today", "who's coming in tomorrow",
"is she working on <day>", "any cancellations", or "which patients
canceled", the classifier returns `("clinic schedules info", "Very High")`
directly — skipping the ~800ms qwen call AND the chroma-induced
`read_calendar` / `delegate_opus` misclassifications seen in the
transcripts.

Guard rails: the fast path intentionally defers to the model when the
prompt contains SMS/email/call verbs ("text my wife the clinic
schedule"), the "tell <someone>" pattern where someone is not "me"/"us",
or genuinely ambiguous follow-ups ("how about tomorrow", "more details
about the first patient") that need FIFO context to resolve.

Addresses: Issues 4 (MEDIUM), 6 (MEDIUM), 7 (MEDIUM), 9 (MEDIUM),
12 (MEDIUM), 13 (MEDIUM), 16 (MEDIUM). Partially addresses Issue 5
(MEDIUM — pronoun "she" still slips through without explicit clinic
keyword).

### `intent_classifier/v3/classifier.py` — delete-intent guard

Added `_is_delete_intent()` + a post-validation guard that demotes
`send email` / `send message` classifications back to `others:Low`
whenever the raw prompt starts with "delete it/that/them/…". This
prevents the failure mode from Issue 15 where "can you delete it for
me" chroma-matched send_email exemplars, invoked the send_email
handler (which has no way to satisfy a delete), and wasted a full
Stage 2 → Stage 3 round trip.

Addresses: Issue 15 (CRITICAL).

### `test_code/test_v3_classifier_rules.py` — unit tests

Added 38 parametrized tests covering:
- Clinic fast-path positive matches for the exact transcript phrasings
  that misrouted on 2026-04-20.
- Negative cases (generic calendar queries, ambiguous follow-ups, empty
  input).
- Send-intent exclusions ("text my wife the clinic schedule" must not
  hijack to the clinic handler).
- Delete-intent matches + rejections (send/read commands, mid-sentence
  "delete" mentions).

All 38 tests pass against the new helpers.

### Issues not fixed this cycle

- **Issue 1 (CRITICAL)** — SMS confirm with no open draft. Needs a
  deeper audit of the draft state lifecycle between server-side
  FIFO (`SEND_MESSAGE_DRAFT_OPEN`) and the Android client's local
  draft store. Likely a draft TTL / reconnect mismatch, not a
  classifier bug. Out of scope for this pass.
- **Issue 2 (MEDIUM)** — "tell my wife that I took out daughter back
  home" classified others:Low on the first try, then correctly as
  send_message on a retry. The chroma training set lacks "tell my
  <family_member>" exemplars; best fix is a seed-DB addition, not a
  code edit.
- **Issue 8 (CRITICAL)** — "how about tomorrow" follow-up that ran
  Stage 3 for 180s. Root cause is the clinic handler not emitting
  STAGE2_FOLLOWUP pending context; the fast path doesn't help
  because "how about tomorrow" has no clinic keywords. Proper fix is
  to stash clinic context into `pending_action` (STAGE2_FOLLOWUP) so
  the resolver catches relative-date follow-ups — larger handler
  refactor.
- **Issue 10 (CRITICAL)** — "casual look like tomorrow" cancelled
  after 2.8s due to client disconnect. STT-error downstream of the
  pipeline; needs stream-reconnect handling in jane_proxy, not
  classifier work.
- **Issue 11 (LOW)** — skipped per instructions; the `.strip("[]")`
  patch in c9819c3 already resolves the bracket form of the same
  problem.
- **Issue 14 (CRITICAL), 17 (MEDIUM), 18 (MEDIUM)** — patient-detail
  ordinal follow-ups. Same root cause as Issue 8: clinic handler
  doesn't emit STAGE2_FOLLOWUP pending with the last patient list,
  so "first patient" has no referent. Needs handler refactor.


