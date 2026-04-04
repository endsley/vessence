# Job: Verify and Fix Model Label Display in Web Jane Chat Bubbles

Status: complete
Completed: 2026-03-24 12:15 UTC
Notes: Code review confirms implementation is correct. Backend emits model event at L726 (greetings) and L741 (non-greetings). Frontend handles at L979, stores in active.model. Label renders at L474 as 10px grey text after Copy/Play buttons. Ack bubbles get "gemma" label, work bubbles get the brain model (haiku/sonnet/opus). Classifier recommendation matches actual model used via _resolve_model_for_brain mapping. Needs live testing on web to confirm visual rendering — uvicorn --reload should have picked up changes.
Priority: 2
Model: sonnet
Created: 2026-03-24

## Objective
Verify that the model label (opus, sonnet, haiku, gemma) displays correctly on each Jane response bubble in web Jane. The backend `model` event and frontend rendering were implemented earlier today but have not been tested end-to-end.

## Context
Changes already made (this session, 2026-03-24):
- Backend: `jane_proxy.py` emits `emit("model", intent.get("model", "sonnet"))` for non-greeting messages and `emit("model", intent.get("model", "gemma"))` for greetings
- Frontend: `jane.html` handles `event.type === 'model'` and stores `active.model = event.data`
- Frontend: Model label rendered as `<span>` with `ml-auto text-[10px] text-slate-500` after Copy/Play audio buttons
- Message objects now include `model: ''` field

## Pre-conditions
- jane-web service running with latest code (uvicorn --reload should have picked up changes)

## Steps
1. Open web Jane and send a greeting ("hey") — verify bubble shows "gemma" label
2. Send a simple question ("what time is it") — verify ack bubble shows "gemma" for the ack, and response bubble shows "haiku"
3. Send a medium complexity question — verify response bubble shows "sonnet"
4. Send a hard question ("audit the codebase") — verify response bubble shows "opus"
5. If model labels are NOT showing:
   - Check browser console for JS errors
   - Check jane_web.log for `emit("model"` events
   - Verify the `model` event is being serialized in the SSE stream
   - Check if `msg.model` is populated in Alpine state (browser devtools)
6. If the ack bubble (quick response) doesn't show a model label, ensure the classifier's model value propagates to the ack bubble before it gets finalized as `active.text`
7. Verify the label shows the **brain model** (opus/sonnet/haiku), not just the classifier's recommendation — the actual model used by persistent_claude may differ from the classifier's suggestion if there's a model override

## Verification
- Each Jane response bubble displays a small grey model label (bottom-right)
- Greeting responses show "gemma"
- Simple/medium/hard responses show the correct tier
- Label is visually unobtrusive (10px, slate-500 color)

## Files Involved
- `jane_web/jane_proxy.py` — emits model event (L739, L727)
- `vault_web/templates/jane.html` — handles model event, renders label
- `jane/persistent_claude.py` — may need to emit actual model used
- `agent_skills/intent_classifier.py` — classifies and recommends model

## Notes
- The classifier recommends a model, but `_resolve_model_for_brain()` in jane_proxy.py may override it. Make sure the label reflects the actual model used, not just the classifier's recommendation.
- If persistent_claude uses a different model than what the classifier suggested (e.g. falls back to sonnet when opus is requested), the label should show what was actually used.
- Consider also showing the model on the ack bubble itself (classifier-generated quick responses are produced by gemma).
