# Most Recent Nightly Self-Improvement

- Run started: 2026-04-25 01:00:01
- Report generated: 2026-04-25 02:10:20
- Total runtime: 4218s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260425_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-25 01:00:01,687 INFO Committed 40 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-25 01:00:01,824 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
- 4. ✓ Pipeline Audit (30 prompts) (19.1m)
  - Problems:
    - Prompts audited: 29.
    - Classification failures: 10.
    - Response failures: 22.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (4.1m)
  - Problems:
    - Transcript review found 11 issues: 10 critical, 1 medium.
    - Send-message turn was routed to Stage 3 and answered as message reading instead of drafting/sending an SMS.
    - Fresh to-do-list request inherited stale category state, causing the Stage 2 todo handler to fail and escalate unnecessarily.
  - Fixes:
    - 2026-04-25 01:38:18,480 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (11 issues)
    - 2026-04-25 01:38:18,481 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 10 critical, 1 medium is...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - [0;93m2026-04-25 02:07:30.419164525 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-04-25 02:07:30.419176092 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-04-25 02:07:30.653838236 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-25 02:08:34,482 INFO Committed 7 file(s).

**Top follow-ups:**

- Normalize classifier aliases before validation (`send_message` -> `send message`) and add a regression test for SMS utterances that include body text.
- Clear todo pending state when a new top-level todo request is detected, and ignore carried category values unless the utterance is only a category reply.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 4 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-25 01:00:01,687 INFO Committed 40 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-25 01:00:01,824 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `timeout`
- Duration: 900s (15.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Job ended with status `timeout`.
- Dead files — review needed: 1.
- Possibly-dead functions: 13.
- Duplicate function bodies: 9 groups.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 1148s (19.1 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 29.
- Classification failures: 10.
- Response failures: 22.
- **user: I was wondering if you can tell me what's on my to-do list
- **user: the home
- **user: how about for the clinic
- ****Summary:**

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
- Duration: 247s (4.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 11 issues: 10 critical, 1 medium.
- Send-message turn was routed to Stage 3 and answered as message reading instead of drafting/sending an SMS.
- Fresh to-do-list request inherited stale category state, causing the Stage 2 todo handler to fail and escalate unnecessarily.
- Clear todo-list request was misclassified as `others`, forcing a 113-second Stage 3 path.
- A simple category follow-up was not resolved by pending_action and instead went through slow Stage 3.

### Improvements It Made

- 2026-04-25 01:38:18,480 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (11 issues)
- 2026-04-25 01:38:18,481 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 10 critical, 1 medium issues. The most urgent was: Sen

### Follow-Up Fixes Recommended

- Normalize classifier aliases before validation (`send_message` -> `send message`) and add a regression test for SMS utterances that include body text.
- Clear todo pending state when a new top-level todo request is detected, and ignore carried category values unless the utterance is only a category reply.
- Add lexical fallback rules for `todo list`/`to-do list` before `others`, and retrain the classifier with more direct todo-list examples.
- When `awaiting=category`, route category-only replies directly to the todo handler and skip Stage 1 classification entirely.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 1800s (30.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- [0;93m2026-04-25 02:07:30.419164525 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-04-25 02:07:30.419176092 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-04-25 02:07:30.653838236 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-04-25 02:07:30.653874525 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-04-25 02:07:30.653884465 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-25 06:07:30 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m

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

- 2026-04-25 02:08:34,482 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
