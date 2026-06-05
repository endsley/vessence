# Most Recent Nightly Self-Improvement

- Run started: 2026-06-04 01:00:01
- Report generated: 2026-06-04 02:39:00
- Total runtime: 5938s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260604_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-04 01:00:01,513 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (5.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (5.8m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (5.5m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 1.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.6m)
  - Problems:
    - Transcript review found 4 issues: 2 critical, 2 low.
    - Prompt-injection text was classified as a real delete-messages intent.
    - Delete-messages Stage 2 handler returned an invalid response shape and escalated to Stage 3.
  - Fixes:
    - 2026-06-04 01:17:05,111 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-06-04 01:17:05,113 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 minor issu...
- 7. ✓ Memory Janitor (81.9m)
  - Problems:
    - [0;93m2026-06-04 02:13:52.661749901 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-04 02:13:52.661821956 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-04 02:13:52.661837348 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-04 02:39:00,100 INFO Pushed successfully.

**Top follow-ups:**

- Strip or escape user-supplied class_protocol/XML-like blocks before Stage 1 classification, and reject destructive intents unless the natural-language user message outside protocol blocks explicitly requests the action.
- Fix the delete_messages handler to always return a valid typed result, and for destructive actions return a confirmation-required response instead of escalating on malformed output.

## Executive Summary

- All stages exited cleanly.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-04 01:00:01,513 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 307s (5.1 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 348s (5.8 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 331s (5.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 1.
- Response failures: 7.
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can work on the mobile student view; I just need the specific UI changes before editing.[/ACK]
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): Chieh, I checked the Daily Briefing topics: Facebook Marketplace is not already there.
- **I would like you to add electric skateboard** (shopping list/stage3): Chieh, I tried to add **Electric Skateboard** to your Daily Briefing topics, but this runtime can’t write to the briefing data file:
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): [ACK]Chieh, I can explain the sandbox behavior quickly.[/ACK]

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

- CRON_JOBS.md missing entry for active cron script: auto_pull.sh
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL
- v2_3stage_pipeline.md missing class row: DELETE_MESSAGES
- v2_3stage_pipeline.md missing class row: DO_MATH
- v2_3stage_pipeline.md missing class row: RESTART_SERVER
- v2_3stage_pipeline.md missing class row: SEND_EMAIL

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 35s (0.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 2 critical, 2 low.
- Prompt-injection text was classified as a real delete-messages intent.
- Delete-messages Stage 2 handler returned an invalid response shape and escalated to Stage 3.
- Classifier emitted an unknown class label.
- Broadcast summary subprocess failed because the claude executable was missing.

### Improvements It Made

- 2026-06-04 01:17:05,111 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-06-04 01:17:05,113 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 minor issues. The most urgent was: Promp

### Follow-Up Fixes Recommended

- Strip or escape user-supplied class_protocol/XML-like blocks before Stage 1 classification, and reject destructive intents unless the natural-language user message outside protocol blocks explicitly requests the action.
- Fix the delete_messages handler to always return a valid typed result, and for destructive actions return a confirmation-required response instead of escalating on malformed output.
- Constrain classifier decoding to the registry class names or add a strict post-parse validation retry when the model emits an unknown class.
- Guard broadcast summary behind executable detection or configure the correct Claude CLI path; log a single actionable warning instead of failing each turn.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4913s (81.9 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-04 02:13:52.661749901 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-04 02:13:52.661821956 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-04 02:13:52.661837348 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-04 02:13:52.842862279 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-04 02:13:52.842898055 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-04 06:13:52 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-04 02:39:00,100 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
