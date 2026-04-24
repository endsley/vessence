# Transcript Quality Review — 2026-04-23

Generated: 2026-04-24 01:27:05

## Issue 1 [MEDIUM]

**Turn:** 2026-04-23 01:18:44
**User said:** I was wondering if you can tell me what's on my to-do list

**Problem:** Stage 1 misclassified a clear to-do-list request as `others`, so the fast-path to-do handler never ran.

**Root cause:** The classifier labeled the turn `others:Low` and immediately escalated to Stage 3 with no to-do class protocol loaded. Jane still recovered the intent in Stage 3, but only after a slower full-LLM path.

**Suggested fix:** Add lexical/rule fallback for `to do`, `to-do`, and `todo list` phrases before `others`, and retrain the Stage 1 examples so list-reading requests map to `todo list` reliably.

**Log evidence:**
```
[2026-04-23 01:18:44] (audit-177692) user: I was wondering if you can tell me what's on my to-do list
```
```
2026-04-23 01:18:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (860ms)
```
```
2026-04-23 01:18:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1408 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-23 01:19:10
**User said:** the home

**Problem:** Follow-up routing failed: the user's category answer was not sent directly to the pending to-do flow.

**Root cause:** After Jane asked which category to hear, the next turn should have been claimed by `pending_action_resolver`. Instead there is no resolver hit, Stage 1 ran again, classified `the home` as `others:Low`, and Stage 3 had to infer the answer from recent history.

**Suggested fix:** When Stage 2 or Stage 3 asks a constrained follow-up like a to-do category, persist a pending action and bypass Stage 1 entirely on the next user turn.

**Log evidence:**
```
[2026-04-23 01:19:10] (audit-177692) user: the home
```
```
2026-04-23 01:19:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (788ms)
```
```
2026-04-23 01:19:10 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=2001 sid_override=True class_protocol=n/a
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-23 01:19:27
**User said:** how about for the clinic

**Problem:** Jane returned an incorrect clinic to-do list count and duplicated one item.

**Root cause:** This follow-up also missed the to-do fast path and went through Stage 3 (`others:Low`, `class_protocol=n/a`). The spoken answer says there are 6 clinic items and repeats `Add texting capability to the laptop`, while the later source-of-truth summary says there are 5 unique clinic items.

**Suggested fix:** Force all to-do reads, including Stage 3 fallbacks, through the same `todo_list_cache.json` reader/deduper used by Stage 2, and deduplicate items before rendering speech.

**Log evidence:**
```
[2026-04-23 01:19:27] (audit-177692) user: how about for the clinic
```
```
[2026-04-23 01:19:27] (audit-177692) user: how about for the clinic jane: 6 items for the clinic. Curtain rods at kathia’s clinic; The wooden block for the door at the clinic; Create a clinic Gmail account; Put mirrors up; Add texting capability to the laptop; and finally, Add texting capability to the laptop.
```
```
2026-04-23 01:19:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1374ms)
```
```
[2026-04-23 01:21:17] (audit-177692) **Summary:** Stage 2 and 3 use Google Docs (synced to `todo_list_cache.json` every 30 min) as the single source of truth for todos. Home todos: Put TV from Kathia's room to gym, Clean downstairs, Rebuild the bed. Clinic todos contain 5 unique items
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-04-23 01:30:56
**User said:** what's the weather like tomorrow

**Problem:** Stage 1 misclassified a straightforward weather request as `others`, bypassing the weather fast path.

**Root cause:** The server routed the turn to Stage 3 even though the utterance is an explicit forecast query. Jane answered, but only through a slower, unnecessary escalation path.

**Suggested fix:** Expand Stage 1 weather training/examples for phrasings like `what's the weather like tomorrow` and add a keyword fallback for `weather`, `forecast`, `tomorrow`, and `rain` patterns.

**Log evidence:**
```
[2026-04-23 01:30:56] (audit-177692) user: what's the weather like tomorrow
```
```
2026-04-23 01:30:55 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (764ms)
```
```
2026-04-23 01:30:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1320 sid_override=True class_protocol=n/a
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-04-23 09:35:01
**User said:** can you set a timer for 23 minutes

**Problem:** A simple timer request entered a broken multi-turn loop after the timer was already set.

**Root cause:** Stage 2 parsed the duration correctly but still asked for a label (`duration=1380000 but no label → ask`). After the follow-up, the handler fired the timer, but the returned `[TOOL_RESULT:...]` was fed back into Stage 1 as if it were a new user turn. Stage 1 classified that tool result as another timer request, Stage 2 parsed `duration_ms=0`, and Jane asked for duration again. The logs also show resolver hits followed by Stage 1 runs, so follow-up routing is not actually bypassing classification.

**Suggested fix:** Make timer labels optional for `set a timer` requests, consume `[TOOL_RESULT:...]` messages out-of-band so they never enter Stage 1, and when `pending_action_resolver` matches a follow-up, short-circuit directly to the target handler without reclassification.

**Log evidence:**
```
2026-04-23 09:35:01 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=1380000 from prompt='can you set a timer for 23 minutes'
```
```
2026-04-23 09:35:01 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: duration=1380000 but no label → ask
```
```
2026-04-23 09:35:10 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → timer (awaiting=label)
```
```
2026-04-23 09:35:11 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: fire duration_ms=1380000 label=''
```
```
2026-04-23 09:35:12 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=0 from prompt='[TOOL_RESULT:{"tool":"timer.set","call_id":"b35f8793-6aef-4e38-9eb6-b7a6da6d2c97","status":"completed","message":"timer '
```
```
2026-04-23 09:35:12 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: timer intent with no duration → ask
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-23 12:28:50
**User said:** okay what is on my to do list

**Problem:** The same to-do-list classification failure recurred in a separate session.

**Root cause:** This later request was again labeled `others:Low` and escalated to Stage 3 instead of using the deterministic to-do handler. That shows the Stage 1 bug is systematic, not a one-off.

**Suggested fix:** Fix Stage 1 intent coverage for `what is on my to do list` style requests and add a regression test that asserts these phrases hit the `todo list` class.

**Log evidence:**
```
[2026-04-23 12:28:50] (jane_android) [private turn — class: clinic schedules info] user: okay what is on my to do list
```
```
2026-04-23 12:28:49 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (760ms)
```
```
2026-04-23 12:28:50 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=907 sid_override=True class_protocol=n/a
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-04-23 18:39:11
**User said:** what's on Maya to do list

**Problem:** A new to-do-list question was hijacked by a stale read-calendar follow-up, and Jane answered the wrong task.

**Root cause:** The resolver incorrectly claimed the turn as `read calendar (awaiting=event_detail)`, Stage 1 then classified the utterance as `read calendar:Very High`, the read-calendar handler returned an invalid shape, and Stage 3 was invoked with `class_protocol=loaded:read_calendar`. Jane ultimately answered with the generic to-do categories, ignoring the `Maya` qualifier, and the system even emitted a Bing query built from the internal `read_calendar` class protocol text.

**Suggested fix:** Tighten `pending_action_resolver` so it only captures semantically compatible replies, clear stale follow-ups on topic changes, validate handler return shapes before fallback, and block any web/tool call that is derived from internal class-protocol text rather than the user utterance.

**Log evidence:**
```
[2026-04-23 18:39:11] (jane_android) user: what's on Maya to do list
```
```
2026-04-23 18:39:09 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → read calendar (awaiting=event_detail)
```
```
2026-04-23 18:39:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 read calendar:Very High (817ms)
```
```
2026-04-23 18:39:10 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'read calendar' returned invalid shape → Stage 3
```
```
2026-04-23 18:39:10 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read calendar:Very High voice=False prompt_len=2055 sid_override=True class_protocol=loaded:read_calendar
```
```
2026-04-23 18:39:11 INFO [primp] response: https://www.bing.com/search?q=%3Cclass_protocol+name%3D%22read_calendar%22%3E%0AThese+are+runtime+instructions+for+handling+a+read+calendar+request.
```

---

