# Most Recent Nightly Self-Improvement

- Run started: 2026-05-23 01:00:02
- Report generated: 2026-05-23 02:09:28
- Total runtime: 4165s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260523_010002.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-23 01:00:02,418 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (9.5m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (8.7m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 1.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.3m)
  - Problems:
    - Transcript review found 4 issues: 3 critical, 1 medium.
    - User request took ~2m32s to resolve, making the interaction unusable for real-time use.
    - Turn took ~88s before completion despite no explicit tool invocation in the logs.
  - Fixes:
    - 2026-05-23 01:24:37,062 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-05-23 01:24:37,063 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium iss...
- 7. ✓ Memory Janitor (44.6m)
  - Problems:
    - 3 01:49:30.532862071 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:49:30 WARNING] ModelImporter.cpp:739: Make sure input token...
    - [0;93m2026-05-23 01:51:58.463941922 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-23 01:51:58.464003133 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 12 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.2m)
  - Fixes:
    - 2026-05-23 02:09:18,390 INFO Committed 6 file(s).
    - 2026-05-23 02:09:27,633 INFO Pushed successfully.

**Top follow-ups:**

- Add per-stage timing instrumentation inside Stage 3 (LLM call vs tool call vs postprocessing), enforce a hard timeout with graceful partial-response fallback, and retry/failover policy for stalled frontier-brain responses.
- Introduce a deterministic "system_identity/model_query" handler for this common class of questions or cache static answers, and set a shorter Stage 3 SLA budget for simple factual prompts.

## Executive Summary

- All stages exited cleanly.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-23 01:00:02,418 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 570s (9.5 min)

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

- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 520s (8.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 1.
- Response failures: 1.
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I took a first pass through `~/code/waterlily`.

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
- Duration: 19s (0.3 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 3 critical, 1 medium.
- User request took ~2m32s to resolve, making the interaction unusable for real-time use.
- Turn took ~88s before completion despite no explicit tool invocation in the logs.
- Classifier emitted an unsupported class (`force stage3`) and fell back to `others`, reducing routing fidelity.
- High end-to-end latency again (~74.6s) on an intent-only query.

### Improvements It Made

- 2026-05-23 01:24:37,062 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-05-23 01:24:37,063 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium issues. The most urgent was: User

### Follow-Up Fixes Recommended

- Add per-stage timing instrumentation inside Stage 3 (LLM call vs tool call vs postprocessing), enforce a hard timeout with graceful partial-response fallback, and retry/failover policy for stalled frontier-brain responses.
- Introduce a deterministic "system_identity/model_query" handler for this common class of questions or cache static answers, and set a shorter Stage 3 SLA budget for simple factual prompts.
- Version and harden the Stage 1 class schema: add canonical mappings/aliases for `force stage3` (and similar control-intent tokens), and fail closed with explicit telemetry when unseen labels are returned instead of silently coercing to `others`.
- As above for Stage 3 SLA: split Stage 3 latency budgets by query type and route static/meta-model questions to a cheap deterministic response path.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2679s (44.6 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- 3 01:49:30.532862071 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:49:30 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-23 01:51:58.463941922 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-23 01:51:58.464003133 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-23 01:51:58.464017789 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-23 01:51:58.661862596 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-23 05:51:58 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 12 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 10s (0.2 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-23 02:09:18,390 INFO Committed 6 file(s).
- 2026-05-23 02:09:27,633 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
