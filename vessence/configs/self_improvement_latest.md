# Most Recent Nightly Self-Improvement

- Run started: 2026-06-21 01:00:01
- Report generated: 2026-06-21 02:34:31
- Total runtime: 5670s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260621_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-21 01:00:03,486 INFO Committed 3 file(s).
- 2. ✗ Code Auditor (1.7m)
  - Problems:
    - 2026-06-21 01:01:44,711 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' re...
- 3. ✓ Dead Code Auditor (7.0m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 4.
    - Response failures: 5.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.7m)
  - Problems:
    - Transcript review found 4 issues: 1 critical, 2 low, 1 medium.
    - Stage 1 classifier emitted an unsupported intent label before falling back to others.
    - Stage 1 classifier emitted another unsupported intent label before fallback.
  - Fixes:
    - 2026-06-21 01:29:32,164 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-06-21 01:29:32,166 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium, 2...
- 7. ✓ Memory Janitor (65.0m)
  - Problems:
    - tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
    - [0;93m2026-06-21 02:03:28.779336433 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-21 02:03:28.779384913 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Problems:
    - 2026-06-21 02:34:31,745 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address
  - Fixes:
    - 2026-06-21 02:34:31,467 INFO Committed 5 file(s).

**Top follow-ups:**

- Constrain classifier output to the supported enum, and add explicit normalization/tests for project/source-code questions so they route cleanly to others without warnings.
- Harden the classifier prompt/parser to only emit valid labels, and add a regression case for architecture/meta questions.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-21 01:00:03,486 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 101s (1.7 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-21 01:01:44,711 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 421s (7.0 min)

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
- Prompts audited: 7.
- Classification failures: 4.
- Response failures: 5.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what “it” is first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, quick answer: yes, you’re asking about the Stage 3 brain process model.[/ACK]
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as authoritative and verify against it before making claims or changes.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll audit both projects’ mobile patterns and patch Waterlily’s responsive UI end to end; this will take a while.[/ACK]I’m going to locate

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
- v2_3stage_pipeline.md missing class row: NATIONALGRID_BILLS
- v2_3stage_pipeline.md missing class row: RESTART_SERVER

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 44s (0.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 1 critical, 2 low, 1 medium.
- Stage 1 classifier emitted an unsupported intent label before falling back to others.
- Stage 1 classifier emitted another unsupported intent label before fallback.
- Stage 3 request completed with very high latency.
- Stage 3 failed to deliver a response before the client disconnected.

### Improvements It Made

- 2026-06-21 01:29:32,164 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-06-21 01:29:32,166 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier output to the supported enum, and add explicit normalization/tests for project/source-code questions so they route cleanly to others without warnings.
- Harden the classifier prompt/parser to only emit valid labels, and add a regression case for architecture/meta questions.
- Move short_term_extractor off the user-facing request path, or enforce a short total timeout and run memory extraction asynchronously after streaming completes.
- For long coding tasks, acknowledge quickly and hand off to an asynchronous job with progress updates instead of holding the voice/chat stream open. Also decouple memory extraction from the live response path.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3898s (65.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-21 02:03:28.779336433 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-21 02:03:28.779384913 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-21 02:03:28.779401050 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:03:28 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-21 02:16:31.525271135 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-21 06:16:31 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- 2026-06-21 02:34:31,745 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address

### Improvements It Made

- 2026-06-21 02:34:31,467 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
