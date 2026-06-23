# Most Recent Nightly Self-Improvement

- Run started: 2026-06-23 01:00:01
- Report generated: 2026-06-23 03:25:15
- Total runtime: 8712s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260623_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.1m)
  - Fixes:
    - 2026-06-23 01:00:06,428 INFO Committed 9 file(s).
- 2. ✓ Code Auditor (5.6m)
  - Problems: none detected
  - Fixes: none applied
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
- 6. ✓ Transcript Quality Review (3.5m)
  - Problems:
    - Transcript review found 5 issues: 3 critical, 1 low, 1 medium.
    - Stage 1 emitted an unsupported intent label before falling back to others.
    - Stage 1 emitted an unsupported 'force stage3' label, then Stage 3 took 163 seconds for a direct architecture question.
  - Fixes:
    - 2026-06-23 01:36:27,075 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-06-23 01:36:27,076 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium, 1...
- 7. ✓ Memory Janitor (108.8m)
  - Problems:
    - [0;93m2026-06-23 03:04:36.876730421 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-23 03:04:36.876772181 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-23 03:04:36.876788014 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 16 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Problems:
    - 2026-06-23 03:25:14,750 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address
  - Fixes:
    - 2026-06-23 03:25:14,454 INFO Committed 6 file(s).

**Top follow-ups:**

- Constrain classifier output to the allowed enum, or add an explicit alias mapping for project/web automation requests to a supported Stage 3 category.
- Add a valid 'stage3_direct' or equivalent class for meta/architecture questions, and instrument Stage 3 with model/context/tool subspans plus an SLA timeout or progress response.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 4s (0.1 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-23 01:00:06,428 INFO Committed 9 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 334s (5.6 min)

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
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need one quick detail first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the Stage 3 brain process behavior against the code quickly.[/ACK]I found the switch points: Stage 3 delegates through `jane_p
- **use the source code as your guide** (todo list/stage3): [ACK]Understood, Chieh — I’ll use the source code as the guide for repo work.[/ACK]
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): `

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/pipeline_audit_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_pipeline_audit_100.log

## Stage 5: Doc Drift Auditor

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Compared source-of-truth docs against live cron, class, and file state to catch stale documentation.

### Problems It Found

- CRON_JOBS.md missing entry for active cron script: auto_pull.sh
- CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
- CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- CRON_JOBS.md missing entry for active cron script: nutricost_deal_monitor.py
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL
- v2_3stage_pipeline.md missing class row: DELETE_MESSAGES

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 210s (3.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 3 critical, 1 low, 1 medium.
- Stage 1 emitted an unsupported intent label before falling back to others.
- Stage 1 emitted an unsupported 'force stage3' label, then Stage 3 took 163 seconds for a direct architecture question.
- Multi-turn context and source-code context were not provided for a follow-up instruction.
- Project familiarization was handled by Stage 3 without logged project context and took 220 seconds.

### Improvements It Made

- 2026-06-23 01:36:27,075 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-06-23 01:36:27,076 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier output to the allowed enum, or add an explicit alias mapping for project/web automation requests to a supported Stage 3 category.
- Add a valid 'stage3_direct' or equivalent class for meta/architecture questions, and instrument Stage 3 with model/context/tool subspans plus an SLA timeout or progress response.
- Load conversation history by session id before Stage 3, and route source-code requests to a workspace-aware code path that attaches repository context or invokes the code agent.
- Detect project/codebase familiarization requests and route them to a code-aware worker with repository access. Move short-term memory extraction off the latency-sensitive path or cap it to a short asynchronous attempt.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 6526s (108.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-23 03:04:36.876730421 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-23 03:04:36.876772181 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-23 03:04:36.876788014 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:36 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-23 03:04:37.102005658 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:37 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-23 03:04:37.109344284 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-23 07:04:37 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 16 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- 2026-06-23 03:25:14,750 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address

### Improvements It Made

- 2026-06-23 03:25:14,454 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
