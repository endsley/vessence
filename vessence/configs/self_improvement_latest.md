# Most Recent Nightly Self-Improvement

- Run started: 2026-06-27 01:00:01
- Report generated: 2026-06-27 04:48:58
- Total runtime: 13734s
- Jobs: 8 total, 5 ok, 2 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260627_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-27 01:00:03,677 INFO Committed 4 file(s).
- 2. ✗ Code Auditor (2.3m)
  - Problems:
    - 2026-06-27 01:02:19,400 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' retu...
- 3. ✓ Dead Code Auditor (7.2m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
    - CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- 6. ✓ Transcript Quality Review (1.3m)
  - Problems:
    - Transcript review found 9 issues: 3 critical, 3 low, 3 medium.
    - Stage 1 emitted an unsupported intent label before falling back to others
    - Stage 1 emitted an unsupported intent label before falling back to others
  - Fixes:
    - 2026-06-27 01:30:51,973 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-06-27 01:30:52,064 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 3 medium, 3...
- 7. ⏱ Memory Janitor (196.8m)
  - Problems:
    - [0;93m2026-06-27 01:39:12.647669470 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-27 01:39:12.955062255 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-27 01:39:12.955100791 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
- 8. ✓ Auto-Commit + Push (post) (1.2m)
  - Fixes:
    - 2026-06-27 04:48:52,819 INFO Committed 7 file(s).
    - 2026-06-27 04:48:56,062 INFO Pushed successfully.

**Top follow-ups:**

- Constrain classifier outputs to the allowed enum at decode/prompt level, or add a supported project/web_work intent that deliberately escalates to Stage 3.
- Teach the classifier that meta/system questions should classify as others, or add a valid force_stage3 internal route instead of allowing free-form labels.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-27 01:00:03,677 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 136s (2.3 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-27 01:02:19,400 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 431s (7.2 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups

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
- Classification failures: 3.
- Response failures: 4.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know which payment you mean.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the stage 3 brain runtime path in the code before answering; this should be quick.[/ACK]I’m searching the runtime entrypoints
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the ground truth and verify behavior against it before making claims.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll inspect Waterlily and the education project mobile patterns first, then implement responsive mobile UIs across the site; this will ta

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/pipeline_audit_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_pipeline_audit_100.log

## Stage 5: Doc Drift Auditor

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Compared source-of-truth docs against live cron, class, and file state to catch stale documentation.

### Problems It Found

- CRON_JOBS.md missing entry for active cron script: auto_pull.sh
- CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
- CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- CRON_JOBS.md missing entry for active cron script: nutricost_deal_monitor.py
- CRON_JOBS.md claims run_kathia_schedule.py is active but no matching cron entry exists
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 78s (1.3 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 3 critical, 3 low, 3 medium.
- Stage 1 emitted an unsupported intent label before falling back to others
- Stage 1 emitted an unsupported intent label before falling back to others
- Stage 3 response latency was excessive for a short meta question
- Stage 3 response latency was high for a short follow-up

### Improvements It Made

- 2026-06-27 01:30:51,973 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-06-27 01:30:52,064 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 3 medium, 3 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier outputs to the allowed enum at decode/prompt level, or add a supported project/web_work intent that deliberately escalates to Stage 3.
- Teach the classifier that meta/system questions should classify as others, or add a valid force_stage3 internal route instead of allowing free-form labels.
- Add a lightweight deterministic handler for runtime/meta-status questions, or enforce a shorter Stage 3 timeout with a partial/status response for voice and chat clients.
- Keep the persistent Stage 3 process warm and add health checks around the CLI LLM adapter so slow or wedged calls fail fast before blocking the user turn.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 11811s (196.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- [0;93m2026-06-27 01:39:12.647669470 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-27 01:39:12.955062255 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-27 01:39:12.955100791 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:12 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-27 01:39:13.537922181 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:13 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-27 01:39:13.537974000 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-27 05:39:13 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 70s (1.2 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-27 04:48:52,819 INFO Committed 7 file(s).
- 2026-06-27 04:48:56,062 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
