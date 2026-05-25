# Transcript Quality Review — 2026-05-24

Generated: 2026-05-25 01:23:41

## Issue 1 [MEDIUM]

**Turn:** 2026-05-24 01:17:46
**User said:** can you tell me if currently you are using cold decks or Claude cold as the base

**Problem:** Simple model-status question went to generic Stage 3 and took 100.988s.

**Root cause:** Stage 1 classified the turn as `others:Low`; no Stage 2 system/model-status handler handled it, so it escalated to the OpenAI Stage 3 brain. The end-to-end log shows a very slow response for a question that should be answered from local configuration.

**Suggested fix:** Add a `model_status` or `system_status` intent plus a deterministic Stage 2 handler that reads the actual configured Stage 3 brain from runtime config/env and returns it directly. Include STT variants such as `codex`, `cold decks`, `Claude code`, and `Jane Web`.

**Log evidence:**
```
2026-05-24 01:17:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1633ms) params={}
```
```
2026-05-24 01:17:45 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-24 01:17:45 INFO [jane.proxy] [audit-177959] stream_message brain=OpenAI history=0 msg_len=94 file_ctx=False
```
```
2026-05-24 01:19:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (100988ms)
```

---

## Issue 2 [LOW]

**Turn:** 2026-05-24 01:19:45
**User said:** currently which large language model is being used as Jane Webb

**Problem:** Stage 1 emitted an invalid class label before falling back to `others`.

**Root cause:** The classifier returned `force stage3`, which is not in the accepted category schema. The fallback preserved behavior by mapping it to `others`, but the classifier prompt/schema and validator are out of sync.

**Suggested fix:** Constrain the classifier prompt/decoder to the allowed labels, or add an explicit validator mapping from `force stage3` to the canonical escalation category before logging it as unknown.

**Log evidence:**
```
2026-05-24 01:19:43 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-24 01:19:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1275ms) params={}
```
```
2026-05-24 01:19:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=63 sid_override=True class_protocol=n/a
```

---

