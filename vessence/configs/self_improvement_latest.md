# Most Recent Nightly Self-Improvement

- Run started: 2026-06-01 01:00:01
- Report generated: 2026-06-01 01:30:54
- Total runtime: 1852s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260601_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-01 01:00:02,109 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (11.5m)
  - Problems:
    - 2026-06-01 01:11:33,763 [WARNING] All fix attempts exhausted, reverting
- 3. ✓ Dead Code Auditor (6.6m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (4.7m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 1.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.3m)
  - Fixes:
    - 2026-06-01 01:23:08,955 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-06-01 01:23:08,957 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ✓ Memory Janitor (7.7m)
  - Problems:
    - [0;93m2026-06-01 01:24:07.609855135 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-01 01:24:07.609922328 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-01 01:24:07.609941345 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 2 code-related memories one at a time. Skipped 200 recent...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-01 01:30:54,694 INFO Pushed successfully.

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

- 2026-06-01 01:00:02,109 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 691s (11.5 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-06-01 01:11:33,763 [WARNING] All fix attempts exhausted, reverting

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 394s (6.6 min)

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
- Duration: 279s (4.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 1.
- Response failures: 3.
- **codex timing** (others/stage3): Chieh, do you mean Codex response latency, or do you want me to time a specific command/task? [[AWAITING:codex_timing_scope
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): Got it, Chieh. I’ll add a helpful, student-facing `Hint` section for each question that nudges the solving approach without giving away the answer.
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can make those mobile student UI changes once you give me the exact screens and desired behavior.[/ACK]

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
- Duration: 20s (0.3 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-01 01:23:08,955 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-06-01 01:23:08,957 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 464s (7.7 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-01 01:24:07.609855135 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-01 01:24:07.609922328 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-01 01:24:07.609941345 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-01 01:24:07.870364007 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-01 01:24:07.870403319 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-01 05:24:07 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 2 code-related memories one at a time. Skipped 200 recently verified entries. All checked o

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

- 2026-06-01 01:30:54,694 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
