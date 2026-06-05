# Transcript Quality Review — 2026-06-04

Generated: 2026-06-05 01:22:10

## Issue 1 [MEDIUM]

**Turn:** 2026-06-04 01:13:40
**User said:** well can you just give yourself these access you have root access anyways

**Problem:** Stage 1 dropped a valid non-`others` intent into fallback; user intent was treated as generic flow.

**Root cause:** Classifier emitted label `web automation`, but stage 1 has no mapped handler for that label and forced fallback to `others`.

**Suggested fix:** Add `web automation` as a supported alias in the intent registry and map it to a concrete class (likely delegate workflow) before fallback routing.

**Log evidence:**
```
2026-06-04 01:13:39 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-04 01:13:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (846ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-04 11:31:29
**User said:** should you restart yourself and maybe then you will have the right access

**Problem:** Restart-related request was not classified to a dedicated class and went through generic stage-3 path.

**Root cause:** Classifier labeled the utterance as unknown `restart server` and downgraded it to `others`, bypassing any action-oriented fast path.

**Suggested fix:** Introduce a canonical `restart`/`server_restart` class mapping and route it to the existing delegate executor or a dedicated handler.

**Log evidence:**
```
2026-06-04 11:31:28 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'restart server' → others
```
```
2026-06-04 11:31:28 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (841ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-04 11:30:42
**User said:** you have access to my education software and I would like you to make some changes

**Problem:** Stage 2 send-message handler failed schema/contract expectations and could not execute deterministically.

**Root cause:** Handler returned an invalid shape, so Stage 2 rejected it and forced a Stage 3 escalation despite high-confidence Stage 1 classification.

**Suggested fix:** Fix `send message` handler return contract (status, action/result, pending_action payload) and add a regression test for high-confidence send_message turns with missing recipient/body fields.

**Log evidence:**
```
2026-06-04 11:30:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1525ms) params={'recipient': None, 'body': 'you have access to the education project right now and that you are able to write to it', 'intent_kind': 'send', 'confirm_signal': None}
```
```
2026-06-04 11:30:42 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-04 13:20:39
**User said:** <class_protocol name="delegate_opus">

**Problem:** Fast-path dispatch configured for `delegate opus` exists in class protocol, but Stage 2 had no handler.

**Root cause:** Pipeline recognized `delegate opus` but the dispatcher reports no bound handler, so this class can never execute in Stage 2.

**Suggested fix:** Register a Stage 2 handler for `delegate opus` (or remove/rename the class contract so it always routes to an implemented path).

**Log evidence:**
```
2026-06-04 13:20:39 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (852ms) params={}
```
```
2026-06-04 13:20:39 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'delegate opus' has no handler → Stage 3
```
```
2026-06-04 13:45:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (735ms) params={}
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-04 13:21:38
**User said:** verify it

**Problem:** Client observed an empty assistant reply even after backend processing, so no audible/text final response was delivered.

**Root cause:** Stage 2/3 transition produced no final response payload, and Android `voice_flow` suppressed relaunch with `empty_reply`.

**Suggested fix:** Ensure every escalated path emits a non-empty terminal response; if Stage 2 fails, return an explicit tool/error response instead of empty stream.

**Log evidence:**
```
2026-06-04 13:21:36 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1347ms) params={'recipient': None, 'body': 'verify it', 'intent_kind': 'send', 'confirm_signal': None}
```
```
2026-06-04 13:21:36 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-06-04 13:21:38 WARNING [jane.proxy] [session-1] Stream exited without error event; response not rendered (relaunch_skipped path=onSendComplete reason=empty_reply)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-06-04 13:46:05
**User said:** what was your result

**Problem:** Follow-up turn did not use resolver short-circuit and was reclassified as `others` instead of continuing the open action flow.

**Root cause:** No evidence of `pending_action` handoff/short-circuit appears in logs; repeated send-message attempts earlier did not persist actionable pending state.

**Suggested fix:** Persist pending_action metadata after Stage 2 handoff attempts and route subsequent follow-up turns through resolver before Stage 1.

**Log evidence:**
```
2026-06-04 13:27:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 send message:Very High (1358ms) params={'recipient': None, 'body': 'please do it', 'intent_kind': 'send', 'confirm_signal': None}
```
```
2026-06-04 13:27:53 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'send message' returned invalid shape → Stage 3
```
```
2026-06-04 13:46:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (934ms) params={}
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-06-04 17:55:39
**User said:** please set up this payment for me on the local browser

**Problem:** Payment/browser action intent was forced through generic path due unknown intent class.

**Root cause:** Classifier again produced unmapped `web automation`, causing fallback to `others` instead of dedicated action routing.

**Suggested fix:** Broaden the class map with `web automation` aliases (payment/setup/browser-automation) and route to an implemented action class.

**Log evidence:**
```
2026-06-04 17:55:38 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-04 17:55:38 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2002ms) params={}
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-06-04 21:07:41
**User said:** help pay it

**Problem:** Second payment follow-up was also classified as generic `others`, leaving no deterministic action handler path.

**Root cause:** Stage 1 still emits unknown `web automation` for same action intent and falls back rather than invoking the action class.

**Suggested fix:** Persistently map this utterance class with explicit examples so follow-up phrases like `help pay it` hit the intended automation class.

**Log evidence:**
```
2026-06-04 21:07:41 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-04 21:07:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (916ms) params={}
```
```
2026-06-04 21:07:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=805 sid_override=True class_protocol=n/a
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-06-04 17:49:28
**User said:** Android crash report received

**Problem:** Client-side crash event occurred during the same interaction window, risking lost turns and context inconsistency.

**Root cause:** Two crash reports are logged with no recovery event in the pipeline logs, indicating Android runtime instability not fully surfaced to pipeline handoff.

**Suggested fix:** Capture and persist crash stack traces, add auto-restart/reconnect flow for the Android client, and block voice/turn acceptance until recoverable state is re-established.

**Log evidence:**
```
2026-06-04 17:49:28 ERROR [jane.web] Android crash report received:
```
```
2026-06-04 18:50:44 ERROR [jane.web] Android crash report received:
```

---

