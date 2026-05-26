# Most Recent Nightly Self-Improvement

- Run started: 2026-05-25 01:00:01
- Report generated: 2026-05-25 02:52:24
- Total runtime: 6742s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260525_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-25 01:00:01,566 INFO Committed 4 file(s).
- 2. ✗ Code Auditor (8.6m)
  - Problems:
    - 2026-05-25 01:08:35,507 [WARNING] All fix attempts exhausted, reverting
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (6.8m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 1.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.2m)
  - Problems:
    - Transcript review found 2 issues: 1 low, 1 medium.
    - Simple model-status question went to generic Stage 3 and took 100.988s.
    - Stage 1 emitted an invalid class label before falling back to `others`.
  - Fixes:
    - 2026-05-25 01:23:41,351 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (2 issues)
    - 2026-05-25 01:23:41,353 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 1 medium, 1 minor issues....
- 7. ✓ Memory Janitor (88.7m)
  - Problems:
    - [0;93m2026-05-25 02:28:19.971408759 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:19 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-25 02:28:19.971421088 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:19 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-25 02:28:20.148794782 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:20 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-25 02:52:23,967 INFO Pushed successfully.

**Top follow-ups:**

- Add a `model_status` or `system_status` intent plus a deterministic Stage 2 handler that reads the actual configured Stage 3 brain from runtime config/env and returns it directly. Include STT variants such as `codex`, `cold decks`, `Claude code`, and `Jane Web`.
- Constrain the classifier prompt/decoder to the allowed labels, or add an explicit validator mapping from `force stage3` to the canonical escalation category before logging it as unknown.

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

- 2026-05-25 01:00:01,566 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 514s (8.6 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-05-25 01:08:35,507 [WARNING] All fix attempts exhausted, reverting

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

- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 406s (6.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 1.
- Response failures: 1.
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I did a read-only pass over `~/code/waterlily`.

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
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 134s (2.2 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 2 issues: 1 low, 1 medium.
- Simple model-status question went to generic Stage 3 and took 100.988s.
- Stage 1 emitted an invalid class label before falling back to `others`.

### Improvements It Made

- 2026-05-25 01:23:41,351 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (2 issues)
- 2026-05-25 01:23:41,353 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 1 medium, 1 minor issues. The most urgent was: Simple

### Follow-Up Fixes Recommended

- Add a `model_status` or `system_status` intent plus a deterministic Stage 2 handler that reads the actual configured Stage 3 brain from runtime config/env and returns it directly. Include STT variants such as `codex`, `cold decks`, `Claude code`, and `Jane Web`.
- Constrain the classifier prompt/decoder to the allowed labels, or add an explicit validator mapping from `force stage3` to the canonical escalation category before logging it as unknown.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 5320s (88.7 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-25 02:28:19.971408759 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:19 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-25 02:28:19.971421088 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:19 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-25 02:28:20.148794782 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:20 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-25 02:28:20.148836605 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:20 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-25 02:28:20.148848539 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-25 06:28:20 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-25 02:52:23,967 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
