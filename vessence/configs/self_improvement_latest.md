# Most Recent Nightly Self-Improvement

- Run started: 2026-06-16 01:00:01
- Report generated: 2026-06-16 02:27:32
- Total runtime: 5251s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260616_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-16 01:00:02,150 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (3.2m)
  - Problems:
    - 2026-06-16 01:03:13,061 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verif...
- 3. ✓ Dead Code Auditor (6.8m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
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
- 6. ✓ Transcript Quality Review (3.1m)
  - Problems:
    - Transcript review found 7 issues: 1 critical, 3 low, 3 medium.
    - Stage 1 produced an unsupported class before falling back to others.
    - Stage 3 response was very slow for an architecture/status question.
  - Fixes:
    - 2026-06-16 01:33:10,224 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-06-16 01:33:10,225 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 3...
- 7. ✓ Memory Janitor (54.3m)
  - Problems:
    - [0;93m2026-06-16 01:54:50.301357088 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-16 01:54:50.301408859 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-16 01:54:50.301424507 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 9 stale memories out of 14 checked. Stale memories make Ja...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-16 02:27:31,401 INFO Committed 5 file(s).
    - 2026-06-16 02:27:32,839 INFO Pushed successfully.

**Top follow-ups:**

- Constrain classifier output to a strict enum or add an explicit alias map/test for unsupported labels like 'web automation'.
- Answer runtime architecture questions from deterministic config/source inspection when possible, and decouple broadcast summaries from foreground Stage 3 latency with a circuit breaker/backoff.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-16 01:00:02,150 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 191s (3.2 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-16 01:03:13,061 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 409s (6.8 min)

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
- Duration: 187s (3.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 1 critical, 3 low, 3 medium.
- Stage 1 produced an unsupported class before falling back to others.
- Stage 3 response was very slow for an architecture/status question.
- Stage 1 produced another unsupported class.
- Context-dependent follow-up reached Stage 3 with no logged conversation or file context.

### Improvements It Made

- 2026-06-16 01:33:10,224 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-06-16 01:33:10,225 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 3 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier output to a strict enum or add an explicit alias map/test for unsupported labels like 'web automation'.
- Answer runtime architecture questions from deterministic config/source inspection when possible, and decouple broadcast summaries from foreground Stage 3 latency with a circuit breaker/backoff.
- Keep routing directives separate from intent labels, or add a validated 'escalate' field instead of letting the classifier emit pseudo-classes.
- Carry session transcript/source context into Stage 3 calls, or maintain a durable per-session brain keyed by sid and log that context path explicitly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3260s (54.3 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-16 01:54:50.301357088 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-16 01:54:50.301408859 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-16 01:54:50.301424507 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-16 01:54:50.464946449 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-16 01:54:50.464994443 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-16 05:54:50 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 9 stale memories out of 14 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-16 02:27:31,401 INFO Committed 5 file(s).
- 2026-06-16 02:27:32,839 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
