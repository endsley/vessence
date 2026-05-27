# Most Recent Nightly Self-Improvement

- Run started: 2026-05-26 01:00:01
- Report generated: 2026-05-26 02:54:46
- Total runtime: 6885s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260526_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-26 01:00:01,625 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (15.8m)
  - Problems:
    - 2026-05-26 01:10:01,833 [WARNING] Primary LLM failed: CLI timed out after 600s... Attempting fallback.
    - 2026-05-26 01:15:48,763 [WARNING] All fix attempts exhausted, reverting
- 3. ✓ Dead Code Auditor (6.4m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (7.3m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 1.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.3m)
  - Fixes:
    - 2026-05-26 01:29:53,121 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-05-26 01:29:53,122 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ✓ Memory Janitor (84.8m)
  - Problems:
    - [0;93m2026-05-26 02:38:49.219422996 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-26 02:38:49.219476373 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-26 02:38:49.219493723 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-26 02:54:45,048 INFO Committed 6 file(s).
    - 2026-05-26 02:54:46,402 INFO Pushed successfully.

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

- 2026-05-26 01:00:01,625 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 947s (15.8 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-05-26 01:10:01,833 [WARNING] Primary LLM failed: CLI timed out after 600s... Attempting fallback.
- 2026-05-26 01:15:48,763 [WARNING] All fix attempts exhausted, reverting

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 386s (6.4 min)

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
- Duration: 439s (7.3 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 1.
- Response failures: 1.
- **can you tell me if currently you are using cold decks or Claude cold as the base** (others/stage3): Chieh, current base Stage 3 brain is **Codex/OpenAI**, not Claude Code.
- `/home/chieh/ambient/vessence-data/.env` has `JANE_BRAIN=codex`

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
- Duration: 18s (0.3 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-26 01:29:53,121 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-05-26 01:29:53,122 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 5091s (84.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-26 02:38:49.219422996 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-26 02:38:49.219476373 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-26 02:38:49.219493723 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-26 02:38:49.414295464 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-26 02:38:49.414338323 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-26 06:38:49 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-05-26 02:54:45,048 INFO Committed 6 file(s).
- 2026-05-26 02:54:46,402 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
