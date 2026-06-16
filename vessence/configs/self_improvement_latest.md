# Most Recent Nightly Self-Improvement

- Run started: 2026-06-15 01:00:01
- Report generated: 2026-06-15 02:46:50
- Total runtime: 6409s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260615_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-15 01:00:01,654 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (7.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.9m)
  - Problems:
    - Transcript review found 8 issues: 2 critical, 6 medium.
    - Stage 3 did not preserve multi-turn context for a same-session follow-up.
    - Stage 1 emitted an unsupported class and took 8.7 seconds before falling back to others.
  - Fixes:
    - 2026-06-15 01:36:10,957 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-06-15 01:36:10,958 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 6 medium iss...
- 7. ✓ Memory Janitor (70.6m)
  - Problems:
    - [0;93m2026-06-15 02:16:23.765388511 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-15 02:16:23.765435906 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-15 02:16:23.765451198 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-15 02:46:50,317 INFO Pushed successfully.

**Top follow-ups:**

- Hydrate Stage 3 history from the session id before stream_message and persist Stage 3 user/assistant turns immediately after completion. Add an integration test where two turns with the same sid produce history>0 on the second call.
- Constrain classifier output to the supported enum in prompt/schema validation, map known aliases before warning, and enforce a short Stage 1 timeout with immediate others fallback.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-15 01:00:01,654 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 428s (7.1 min)

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
- Duration: 364s (6.1 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups

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
- Response failures: 1.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail.[/ACK]

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
- Duration: 175s (2.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 2 critical, 6 medium.
- Stage 3 did not preserve multi-turn context for a same-session follow-up.
- Stage 1 emitted an unsupported class and took 8.7 seconds before falling back to others.
- Stage 1 emitted an unsupported class and spent 28.9 seconds classifying a complex Stage 3 question.
- The Stage 3 turn started but has no matching completion log before the next user turn.

### Improvements It Made

- 2026-06-15 01:36:10,957 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-06-15 01:36:10,958 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 6 medium issues. The most urgent was: Stag

### Follow-Up Fixes Recommended

- Hydrate Stage 3 history from the session id before stream_message and persist Stage 3 user/assistant turns immediately after completion. Add an integration test where two turns with the same sid produce history>0 on the second call.
- Constrain classifier output to the supported enum in prompt/schema validation, map known aliases before warning, and enforce a short Stage 1 timeout with immediate others fallback.
- Add strict enum decoding for Stage 1 and a fast rule that complex/meta questions route to others without waiting on a long classifier call.
- Attach a request id to every Stage 3 escalation and log completion, cancellation, and errors in a finally block. Serialize or explicitly cancel overlapping Stage 3 turns for the same session.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4237s (70.6 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-15 02:16:23.765388511 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-15 02:16:23.765435906 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-15 02:16:23.765451198 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-15 02:16:23.918095265 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-15 02:16:23.918153810 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-15 06:16:23 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-06-15 02:46:50,317 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
