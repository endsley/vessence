# Most Recent Nightly Self-Improvement

- Run started: 2026-05-04 01:00:01
- Report generated: 2026-05-04 02:11:32
- Total runtime: 4290s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260504_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-04 01:00:02,289 INFO Committed 7 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-05-04 01:00:02,389 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (5.8m)
  - Problems:
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (1.1m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 5.
    - Response failures: 11.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.6m)
  - Problems:
    - Transcript review found 4 issues: 2 critical, 2 medium.
    - Repeated Stage 3 outage caused silence on the entire 01:06:07-01:06:55 open-ended conversation.
    - Follow-up turns lost conversation context; each Stage 3 escalation was sent with `history=0`.
  - Fixes:
    - 2026-05-04 01:09:31,627 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-05-04 01:09:31,628 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium iss...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - [0;93m2026-05-04 01:44:09.618786537 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-04 01:44:09.843305459 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-04 01:44:09.843338018 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-04 02:09:32,107 INFO Committed 5 file(s).

**Top follow-ups:**

- Add a retry and non-stream fallback around Stage 3 calls, and always emit a user-visible failure response when the brain stream dies instead of ending the turn silently.
- When escalating within the same session, attach prior conversation turns to Stage 3 requests instead of always sending `history=0`; add a regression test for multi-turn same-topic follow-ups.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-04 01:00:02,289 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-04 01:00:02,389 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 345s (5.8 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 68s (1.1 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 12.
- Classification failures: 5.
- Response failures: 11.
- **can you do a search for the Uber website for mCP to work with potentially my AI ** (others/stage3):
- **what I want to know is if we can use Jane to order Uber using this mCP** (others/stage3):
- **so basically Uber has an API just not mCP to order rides** (others/stage3):
- **well I sure my article with the app doesn't** (others/stage3):

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/pipeline_audit_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_pipeline_audit_100.log

## Stage 5: Doc Drift Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Compared source-of-truth docs against live cron, class, and file state to catch stale documentation.

### Problems It Found

- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 154s (2.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 2 critical, 2 medium.
- Repeated Stage 3 outage caused silence on the entire 01:06:07-01:06:55 open-ended conversation.
- Follow-up turns lost conversation context; each Stage 3 escalation was sent with `history=0`.
- Stage 1 was prompt-injected and misclassified non-user control text as `greeting:Very High`.
- The greeting Stage 2 handler returned an invalid payload shape instead of a valid structured response or clean escalation.

### Improvements It Made

- 2026-05-04 01:09:31,627 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-05-04 01:09:31,628 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium issues. The most urgent was: Repe

### Follow-Up Fixes Recommended

- Add a retry and non-stream fallback around Stage 3 calls, and always emit a user-visible failure response when the brain stream dies instead of ending the turn silently.
- When escalating within the same session, attach prior conversation turns to Stage 3 requests instead of always sending `history=0`; add a regression test for multi-turn same-topic follow-ups.
- Sanitize or neutralize `class_protocol`/XML-like control markup before classification, and never allow raw user text to trigger protocol loading or class-contract behavior.
- Enforce schema validation on every handler return value and add tests that malformed or adversarial inputs still produce a valid handler result object.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 3600s (60.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- [0;93m2026-05-04 01:44:09.618786537 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-04 01:44:09.843305459 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-04 01:44:09.843338018 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:09 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-04 01:44:10.061563713 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:10 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-04 01:44:10.061610855 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-04 05:44:10 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `timeout`
- Duration: 120s (2.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- Job ended with status `timeout`.

### Improvements It Made

- 2026-05-04 02:09:32,107 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
