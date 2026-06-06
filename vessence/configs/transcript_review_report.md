# Transcript Quality Review — 2026-06-05

Generated: 2026-06-06 01:13:00

## Issue 1 [MEDIUM]

**Turn:** 2026-06-05 01:20:34
**User said:** <class_protocol name="delegate_opus">These are runtime instructions for handling a delegate

**Problem:** High-confidence delegate intent was routed to Stage 3 even though the pipeline has no Stage-2 handler for that class.

**Root cause:** The stage1 model correctly produced `delegate opus:Very High`, but the registry has no handler mapping for that class, so the pipeline forced a Stage 3 handoff (`class 'delegate opus' has no handler -> Stage 3`).

**Suggested fix:** Register a deterministic Stage-2 handler for `delegate opus` or map this class to a safe fallback stage instead of hard-wiring to Stage 3; gate any `class_protocol` passthrough so unsupported classes cannot skip policy checks.

**Log evidence:**
```
2026-06-05 01:20:33 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:Very High (714ms) params={}
```
```
2026-06-05 01:20:33 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'delegate opus' has no handler → Stage 3
```
```
2026-06-05 01:20:34 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=delegate opus:Very High voice=False prompt_len=1368 sid_override=True class_protocol=loaded:delegate_opus
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-05 01:20:54
**User said:** what was your result

**Problem:** A follow-up question was handled as generic classification/execution instead of a direct pending-action resolver path.

**Root cause:** No pending-action resolver log appears; instead logs show ambiguous short-circuit/persistence logic and then Stage-3 escalation, indicating the follow-up was not routed through resolver context.

**Suggested fix:** When a prior turn establishes follow-up context, persist a `pending_action` and force the very next user reply through resolver before Stage 1 so short follow-up questions do not pay classifier latency or lose context.

**Log evidence:**
```
2026-06-05 01:20:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 unclear:Very High (2164ms) params={}
```
```
2026-06-05 01:20:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: unclear short-circuit (classifier verdict)
```
```
2026-06-05 01:20:53 INFO [jane.proxy] [audit-178063] Persistence worker started stage=stage2 cls=unclear user_chars=75 assistant_chars=82
```
```
2026-06-05 01:20:54 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=20 sid_override=True class_protocol=n/a
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-05 01:21:06
**User said:** please set up this payment for me on the local browser

**Problem:** Payment/web-automation intent was collapsed to `others`, so no dedicated handler path was used.

**Root cause:** Classifier warning shows `web automation` returned by qwen but mapped to `others`, and Stage 1 proceeded with `others:Low`, forcing Stage 3 for an action-like request.

**Suggested fix:** Add/repair intent schema for web-automation and payment setup intents and wire to deterministic handler logic (or explicit refusal path) instead of forcing `others` fallback.

**Log evidence:**
```
2026-06-05 01:21:05 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-05 01:21:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (776ms) params={}
```
```
2026-06-05 01:21:06 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-06-05 01:21:27
**User said:** help pay it

**Problem:** Follow-up `help pay it` was not anchored to prior payment intent and again followed generic path.

**Root cause:** The logs show an `unclear` short-circuit then generic `others:Low` escalation for the turn, with no evidence of a pending-action resolver binding the pronoun-based follow-up to the previous setup/pay intent.

**Suggested fix:** Persist the last actionable intent (`payment_setup`) and resolve short follow-ups (`help`, `go ahead`, pronouns) via the pending action handler before classifier Stage 1.

**Log evidence:**
```
2026-06-05 01:21:23 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 unclear:Very High (772ms) params={}
```
```
2026-06-05 01:21:23 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: unclear short-circuit (classifier verdict)
```
```
2026-06-05 01:21:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1396ms) params={}
```
```
2026-06-05 01:21:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=11 sid_override=True class_protocol=n/a
```

---

## Issue 5 [LOW]

**Turn:** 2026-06-05 16:21:40
**User said:** you have access to the water lily Wellness project right

**Problem:** Android client relaunch-to-STT path ended with a `no_match` event, increasing chance of missed next-turn capture.

**Root cause:** After response-driven relaunch, STT restarted (`relaunch_launched`) but returned `no_match`, suggesting wake/voice handoff or timeout handling is failing for immediate continuation turns.

**Suggested fix:** Add a recoverable retry loop/UI prompt when relaunch STT emits `no_match` (e.g., show 'didn't catch that' and reopen with longer timeout), and log whether relaunch path is triggered by TTS completion or user activity.

**Log evidence:**
```
2026-06-05T16:21:38.825Z [voice_flow] voice_flow[send_message] text_len=56 fromVoice=True
```
```
2026-06-05T16:22:02.937Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-06-05T16:22:07.669Z [voice_flow] voice_flow[stt_error] reason=no_match
```

---

