# Most Recent Nightly Self-Improvement

- Run started: 2026-06-06 01:00:01
- Report generated: 2026-06-06 01:49:36
- Total runtime: 2973s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260606_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-06 01:00:01,617 INFO Committed 3 file(s).
- 2. ✗ Code Auditor (4.3m)
  - Problems:
    - 2026-06-06 01:04:21,369 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' retu...
- 3. ✓ Dead Code Auditor (6.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (2.2m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.4m)
  - Problems:
    - Transcript review found 5 issues: 1 low, 4 medium.
    - High-confidence delegate intent was routed to Stage 3 even though the pipeline has no Stage-2 handler for that class.
    - A follow-up question was handled as generic classification/execution instead of a direct pending-action resolver path.
  - Fixes:
    - 2026-06-06 01:13:00,597 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-06-06 01:13:00,598 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 4 medium, 1 minor issues....
- 7. ✓ Memory Janitor (36.5m)
  - Problems:
    - [0;93m2026-06-06 01:35:17.475615545 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-06 01:35:17.475658975 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-06 01:35:17.475675582 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-06 01:49:35,319 INFO Pushed successfully.

**Top follow-ups:**

- Register a deterministic Stage-2 handler for `delegate opus` or map this class to a safe fallback stage instead of hard-wiring to Stage 3; gate any `class_protocol` passthrough so unsupported classes cannot skip policy checks.
- When a prior turn establishes follow-up context, persist a `pending_action` and force the very next user reply through resolver before Stage 1 so short follow-up questions do not pay classifier latency or lose context.

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

- 2026-06-06 01:00:01,617 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 259s (4.3 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-06 01:04:21,369 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 362s (6.0 min)

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
- Duration: 133s (2.2 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

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
- Duration: 22s (0.4 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 1 low, 4 medium.
- High-confidence delegate intent was routed to Stage 3 even though the pipeline has no Stage-2 handler for that class.
- A follow-up question was handled as generic classification/execution instead of a direct pending-action resolver path.
- Payment/web-automation intent was collapsed to `others`, so no dedicated handler path was used.
- Follow-up `help pay it` was not anchored to prior payment intent and again followed generic path.

### Improvements It Made

- 2026-06-06 01:13:00,597 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-06-06 01:13:00,598 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 4 medium, 1 minor issues. The most urgent was: High-co

### Follow-Up Fixes Recommended

- Register a deterministic Stage-2 handler for `delegate opus` or map this class to a safe fallback stage instead of hard-wiring to Stage 3; gate any `class_protocol` passthrough so unsupported classes cannot skip policy checks.
- When a prior turn establishes follow-up context, persist a `pending_action` and force the very next user reply through resolver before Stage 1 so short follow-up questions do not pay classifier latency or lose context.
- Add/repair intent schema for web-automation and payment setup intents and wire to deterministic handler logic (or explicit refusal path) instead of forcing `others` fallback.
- Persist the last actionable intent (`payment_setup`) and resolve short follow-ups (`help`, `go ahead`, pronouns) via the pending action handler before classifier Stage 1.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2192s (36.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-06 01:35:17.475615545 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-06 01:35:17.475658975 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-06 01:35:17.475675582 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-06 01:35:17.663281546 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-06 01:35:17.663325735 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-06 05:35:17 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-06 01:49:35,319 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
