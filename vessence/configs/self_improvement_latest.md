# Most Recent Nightly Self-Improvement

- Run started: 2026-06-05 01:00:01
- Report generated: 2026-06-05 01:57:07
- Total runtime: 3425s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260605_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-05 01:00:04,287 INFO Committed 25 file(s).
- 2. ✓ Code Auditor (6.7m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.2m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (8.7m)
  - Problems:
    - Prompts audited: 19.
    - Classification failures: 5.
    - Response failures: 15.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.5m)
  - Problems:
    - Transcript review found 9 issues: 2 critical, 7 medium.
    - Stage 1 dropped a valid non-`others` intent into fallback; user intent was treated as generic flow.
    - Restart-related request was not classified to a dedicated class and went through generic stage-3 path.
  - Fixes:
    - 2026-06-05 01:22:10,626 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-06-05 01:22:10,628 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 7 medium iss...
- 7. ✓ Memory Janitor (34.9m)
  - Problems:
    - 05 01:42:24.699911329 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:42:24 WARNING] ModelImporter.cpp:739: Make sure input toke...
    - [0;93m2026-06-05 01:46:05.667206563 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-05 01:46:05.667246405 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-05 01:57:06,017 INFO Committed 6 file(s).
    - 2026-06-05 01:57:07,450 INFO Pushed successfully.

**Top follow-ups:**

- Add `web automation` as a supported alias in the intent registry and map it to a concrete class (likely delegate workflow) before fallback routing.
- Introduce a canonical `restart`/`server_restart` class mapping and route it to the existing delegate executor or a dedicated handler.

## Executive Summary

- All stages exited cleanly.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-05 01:00:04,287 INFO Committed 25 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 401s (6.7 min)

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
- Duration: 372s (6.2 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Dead files — review needed: 1.
- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 522s (8.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 19.
- Classification failures: 5.
- Response failures: 15.
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can update the mobile student view; I need the target screens and changes first.[/ACK]
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): [ACK]Got it, Chieh — I can add another Facebook Marketplace search item once I know what to track.[/ACK]
- **I would like you to add electric skateboard** (shopping list/stage3): [ACK]Chieh, quick clarification before I add electric skateboard.[/ACK]
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): [ACK]Chieh, I can clarify the sandbox behavior quickly.[/ACK]

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
- Duration: 28s (0.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 2 critical, 7 medium.
- Stage 1 dropped a valid non-`others` intent into fallback; user intent was treated as generic flow.
- Restart-related request was not classified to a dedicated class and went through generic stage-3 path.
- Stage 2 send-message handler failed schema/contract expectations and could not execute deterministically.
- Fast-path dispatch configured for `delegate opus` exists in class protocol, but Stage 2 had no handler.

### Improvements It Made

- 2026-06-05 01:22:10,626 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-06-05 01:22:10,628 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 7 medium issues. The most urgent was: Clie

### Follow-Up Fixes Recommended

- Add `web automation` as a supported alias in the intent registry and map it to a concrete class (likely delegate workflow) before fallback routing.
- Introduce a canonical `restart`/`server_restart` class mapping and route it to the existing delegate executor or a dedicated handler.
- Fix `send message` handler return contract (status, action/result, pending_action payload) and add a regression test for high-confidence send_message turns with missing recipient/body fields.
- Register a Stage 2 handler for `delegate opus` (or remove/rename the class contract so it always routes to an implemented path).

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2095s (34.9 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- 05 01:42:24.699911329 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:42:24 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-05 01:46:05.667206563 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-05 01:46:05.667246405 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-05 01:46:05.667262956 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-05 01:46:05.823231899 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-05 05:46:05 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-05 01:57:06,017 INFO Committed 6 file(s).
- 2026-06-05 01:57:07,450 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
