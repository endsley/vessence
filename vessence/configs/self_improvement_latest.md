# Most Recent Nightly Self-Improvement

- Run started: 2026-05-20 01:00:01
- Report generated: 2026-05-20 03:30:20
- Total runtime: 9018s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260520_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-20 01:00:02,887 INFO Committed 8 file(s).
- 2. ✓ Code Auditor (4.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.6m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (0.6m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 2.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 9 issues: 3 critical, 6 medium.
    - Follow-up reply was not resolved by pending_action_resolver and fell through to Stage 1/Stage 3.
    - Stage 3 response path was excessively slow for a direct explanatory question.
  - Fixes:
    - 2026-05-20 01:12:28,465 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-05-20 01:12:28,466 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 6 medium iss...
- 7. ✓ Memory Janitor (135.8m)
  - Problems:
    - [0;93m2026-05-20 03:12:32.258468783 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-20 03:12:32.258509572 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-20 03:12:32.258527038 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 20 stale memories out of 20 checked. Stale memories make J...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-20 03:28:20,519 INFO Committed 6 file(s).

**Top follow-ups:**

- Persist pending_action state across Stage 3 follow-up prompts and add resolver decision logging for every turn, including explicit 'no pending action' entries.
- Fix standing_brain vault-state tracking so an unlocked vault does not trigger a full brain restart on every Stage 3 turn; respawn once after unlock and reuse the process.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-20 01:00:02,887 INFO Committed 8 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 246s (4.1 min)

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
- Duration: 396s (6.6 min)

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
- Duration: 34s (0.6 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 2.
- Response failures: 7.
- **yes those articles and maybe just two days** (others/stage3):
- **currently how does your short-term memory work** (others/stage3):
- **how about** (greeting/stage3):
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3):

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
- Duration: 67s (1.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 3 critical, 6 medium.
- Follow-up reply was not resolved by pending_action_resolver and fell through to Stage 1/Stage 3.
- Stage 3 response path was excessively slow for a direct explanatory question.
- Prompt-injection-looking text was classified as greeting with Very High confidence and sent to the greeting handler.
- No Android diagnostic events were captured for a client-side audio/STT complaint.

### Improvements It Made

- 2026-05-20 01:12:28,465 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-05-20 01:12:28,466 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 6 medium issues. The most urgent was: Prom

### Follow-Up Fixes Recommended

- Persist pending_action state across Stage 3 follow-up prompts and add resolver decision logging for every turn, including explicit 'no pending action' entries.
- Fix standing_brain vault-state tracking so an unlocked vault does not trigger a full brain restart on every Stage 3 turn; respawn once after unlock and reuse the process.
- Harden Stage 1 against literal protocol/XML-like user text: strip or escape class_protocol blocks before classification, and add an injection/safety fallback category. Also fix the greeting handler to always return the expected response schema.
- Ensure Android voice_flow and tool_handler diagnostics are uploaded with the same session id and timestamp range whenever voice/STT failures are reported.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 8151s (135.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-20 03:12:32.258468783 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-20 03:12:32.258509572 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-20 03:12:32.258527038 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-20 03:12:32.474426580 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-20 03:12:32.474466344 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-20 07:12:32 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 20 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-20 03:28:20,519 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
