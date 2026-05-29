# Most Recent Nightly Self-Improvement

- Run started: 2026-05-28 01:00:01
- Report generated: 2026-05-28 03:00:02
- Total runtime: 7201s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260528_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-28 01:00:01,633 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (10.7m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.2m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (5.5m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.4m)
  - Problems:
    - Transcript review found 3 issues: 2 critical, 1 medium.
    - Project-edit request was escalated to Stage 3 without file/project context or evidence of executable tooling.
    - Stage 3 latency was far too high for an assistant turn.
  - Fixes:
    - 2026-05-28 01:23:53,977 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (3 issues)
    - 2026-05-28 01:23:53,978 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 1 medium iss...
- 7. ✓ Memory Janitor (96.1m)
  - Problems:
    - [0;93m2026-05-28 02:37:01.228834304 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-28 02:37:01.228882551 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-28 02:37:01.228897410 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-28 03:00:00,329 INFO Committed 6 file(s).
    - 2026-05-28 03:00:02,309 INFO Pushed successfully.

**Top follow-ups:**

- Add an education_project/module_edit intent and handler, or make Stage 3 attach the teaching app/file context and execute audited repo edits with explicit tool logs.
- Use an async project-edit job with immediate acknowledgement and progress events, or add a fast deterministic handler for known module-edit requests.

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

- 2026-05-28 01:00:01,633 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 644s (10.7 min)

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
- Duration: 332s (5.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 2.
- Response failures: 3.
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. This is Jane running through the Codex/standing-brain path, with memory/context injected. If by “cold text” you meant “Codex,” then yes.
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” refers to.[/ACK]
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I can add hint sections, but I need the target questions/file first.[/ACK]

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
- Duration: 83s (1.4 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 3 issues: 2 critical, 1 medium.
- Project-edit request was escalated to Stage 3 without file/project context or evidence of executable tooling.
- Stage 3 latency was far too high for an assistant turn.
- Follow-up turn lost the prior module-edit context.

### Improvements It Made

- 2026-05-28 01:23:53,977 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (3 issues)
- 2026-05-28 01:23:53,978 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 1 medium issues. The most urgent was: Proj

### Follow-Up Fixes Recommended

- Add an education_project/module_edit intent and handler, or make Stage 3 attach the teaching app/file context and execute audited repo edits with explicit tool logs.
- Use an async project-edit job with immediate acknowledgement and progress events, or add a fast deterministic handler for known module-edit requests.
- Pass bounded session history into Stage 3 and store active project-edit state so continuation phrases like "also" route to the same module-edit workflow before classification.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 5765s (96.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-28 02:37:01.228834304 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-28 02:37:01.228882551 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-28 02:37:01.228897410 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-28 02:37:01.404699635 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-28 02:37:01.404741373 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-28 06:37:01 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-28 03:00:00,329 INFO Committed 6 file(s).
- 2026-05-28 03:00:02,309 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
