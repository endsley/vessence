# Most Recent Nightly Self-Improvement

- Run started: 2026-04-26 01:00:01
- Report generated: 2026-04-26 02:10:46
- Total runtime: 4245s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260426_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-26 01:00:01,635 INFO Committed 26 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-26 01:00:01,766 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
- 4. ✓ Pipeline Audit (30 prompts) (18.7m)
  - Problems:
    - Prompts audited: 18.
    - Classification failures: 3.
    - Response failures: 12.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (5.0m)
  - Fixes:
    - 2026-04-26 01:38:46,406 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-04-26 01:38:46,408 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - [0;93m2026-04-26 02:07:59.363854013 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-04-26 02:07:59.363864999 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-04-26 02:07:59.599406388 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-26 02:08:46,868 INFO Committed 7 file(s).

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

- 2026-04-26 01:00:01,635 INFO Committed 26 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-26 01:00:01,766 [WARNING] Working tree has uncommitted changes — skipping audit.

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
- Duration: 1124s (18.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 18.
- Classification failures: 3.
- Response failures: 12.
- ****Class Protocol: Read Calendar**
- ****Class Protocol: Read Calendar**
- **I need clarification. The "new turn" you provided is class protocol metadata (de** (others/stage3):
- ****Class Protocol: Read Calendar**

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
- Duration: 300s (5.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-26 01:38:46,406 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-04-26 01:38:46,408 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

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
- [0;93m2026-04-26 02:07:59.363854013 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-04-26 02:07:59.363864999 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-04-26 02:07:59.599406388 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-04-26 02:07:59.599441320 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-04-26 02:07:59.599451056 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-26 06:07:59 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m

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

- 2026-04-26 02:08:46,868 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
