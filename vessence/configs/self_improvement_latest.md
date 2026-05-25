# Most Recent Nightly Self-Improvement

- Run started: 2026-05-24 01:00:01
- Report generated: 2026-05-24 03:04:17
- Total runtime: 7456s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260524_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-24 01:00:02,354 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (6.9m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (8.2m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 1.
    - Response failures: 2.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.5m)
  - Problems:
    - Transcript review found 5 issues: 1 critical, 1 low, 3 medium.
    - Local project inspection was escalated to Stage 3 without file/project context.
    - Runtime model/status question missed the fast path and went to Stage 3.
  - Fixes:
    - 2026-05-24 01:23:42,815 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-05-24 01:23:42,816 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 1...
- 7. ✓ Memory Janitor (100.5m)
  - Problems:
    - [0;93m2026-05-24 02:37:28.536909034 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-24 02:37:28.536959742 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-24 02:37:28.536975519 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 20 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-24 03:04:17,638 INFO Pushed successfully.

**Top follow-ups:**

- Add local-path/code-project intent detection before escalation: expand ~/ paths, verify the project path, and attach file context or route to the Codex/code-agent backend with that cwd. If the path is inaccessible, fail fast with a clarifying question.
- Add a self_status or model_status classifier category and Stage 2 handler that reads the configured Stage 3 brain/model from the live proxy/config and returns it directly.

## Executive Summary

- All stages exited cleanly.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-24 01:00:02,354 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 412s (6.9 min)

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
- Duration: 365s (6.1 min)

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
- Duration: 489s (8.2 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 1.
- Response failures: 2.
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I looked through `~/code/waterlily`. No edits made.
- **can you tell me if currently you are using cold decks or Claude cold as the base** (others/stage3): Chieh, it’s Codex, not Claude Code.
- Runtime config: `/home/chieh/ambient/vessence-data/.env` has `JANE_BRAIN=codex`.
- Model se

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
- Duration: 152s (2.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 1 critical, 1 low, 3 medium.
- Local project inspection was escalated to Stage 3 without file/project context.
- Runtime model/status question missed the fast path and went to Stage 3.
- Follow-up model question was sent to Stage 3 with no conversation history and took about 2 minutes.
- Stage 1 produced an out-of-schema class before falling back to others.

### Improvements It Made

- 2026-05-24 01:23:42,815 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-05-24 01:23:42,816 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add local-path/code-project intent detection before escalation: expand ~/ paths, verify the project path, and attach file context or route to the Codex/code-agent backend with that cwd. If the path is inaccessible, fail fast with a clarifying question.
- Add a self_status or model_status classifier category and Stage 2 handler that reads the configured Stage 3 brain/model from the live proxy/config and returns it directly.
- Persist and load session history when sid_override=True, and handle model/status questions in Stage 2 with ASR aliases such as codex/cold decks.
- Constrain classifier output to the allowed enum and add parser tests for unknown labels. If force_stage3 is intentional, add it as an explicit alias.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 6033s (100.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-24 02:37:28.536909034 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-24 02:37:28.536959742 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-24 02:37:28.536975519 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-24 02:37:28.745458750 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-24 02:37:28.745496635 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-24 06:37:28 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 20 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-24 03:04:17,638 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
