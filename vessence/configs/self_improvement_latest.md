# Most Recent Nightly Self-Improvement

- Run started: 2026-06-08 01:00:01
- Report generated: 2026-06-08 02:15:29
- Total runtime: 4527s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260608_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-08 01:00:01,983 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (7.5m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.3m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.5m)
  - Problems:
    - Transcript review found 6 issues: 1 critical, 5 medium.
    - Stage 1 routed a Web-automation request as generic `others` instead of a specific intent.
    - User intent to force a full Stage-3 path was not preserved as a recognized protocol (`force stage3` was downgraded).
  - Fixes:
    - 2026-06-08 01:34:22,711 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-06-08 01:34:22,713 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 5 medium iss...
- 7. ✓ Memory Janitor (41.1m)
  - Problems:
    - [0;93m2026-06-08 02:00:09.141793474 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-08 02:00:09.141840560 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-08 02:00:09.141855923 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-08 02:15:27,646 INFO Committed 5 file(s).
    - 2026-06-08 02:15:29,241 INFO Pushed successfully.

**Top follow-ups:**

- Add `web automation` (and aliases) to the stage-1 taxonomy and map it to a dedicated Stage 2/Stage 3 protocol instead of forcing it through `others`.
- Normalize phrases like `force stage3` in stage-1 to a dedicated class and explicitly bind that class to `class_protocol=loaded:delegate_opus` or equivalent escalation behavior.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-08 01:00:01,983 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 448s (7.5 min)

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
- Duration: 379s (6.3 min)

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

- Status: `timeout`
- Duration: 1200s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Job ended with status `timeout`.
- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 3.
- **what was your result** (greeting/stage3): Chieh, I don’t have a prior result visible in this thread. Which result are you asking about? [[AWAITING:which_result
- **please set up this payment for me on the local browser** (web_automation/stage3): [ACK]Chieh, I can help with the payment setup, but I need one detail first.[/ACK]
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail first.[/ACK]

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
- Duration: 32s (0.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 1 critical, 5 medium.
- Stage 1 routed a Web-automation request as generic `others` instead of a specific intent.
- User intent to force a full Stage-3 path was not preserved as a recognized protocol (`force stage3` was downgraded).
- Turn spent ~90s in Stage 3 despite low-complexity clarification, creating severe UX degradation.
- Follow-up context appears not to be carried forward between turns; each Stage 3 call shows zero history.

### Improvements It Made

- 2026-06-08 01:34:22,711 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-06-08 01:34:22,713 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 5 medium issues. The most urgent was: Stag

### Follow-Up Fixes Recommended

- Add `web automation` (and aliases) to the stage-1 taxonomy and map it to a dedicated Stage 2/Stage 3 protocol instead of forcing it through `others`.
- Normalize phrases like `force stage3` in stage-1 to a dedicated class and explicitly bind that class to `class_protocol=loaded:delegate_opus` or equivalent escalation behavior.
- Add a bounded Stage-3 budget (e.g., 20–30s) with progress updates and a deterministic fallback response if exceeded; route short operational requests to lighter handlers when confidence is low but intent is simple.
- Persist and pass conversation history for the same session in Stage 3 calls, and emit explicit pending-action resolver logs when it intercepts turn routing.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2464s (41.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-08 02:00:09.141793474 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-08 02:00:09.141840560 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-08 02:00:09.141855923 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-08 02:00:09.347107176 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-08 02:00:09.347146832 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-08 06:00:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-08 02:15:27,646 INFO Committed 5 file(s).
- 2026-06-08 02:15:29,241 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
