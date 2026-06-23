# Most Recent Nightly Self-Improvement

- Run started: 2026-06-22 01:00:01
- Report generated: 2026-06-22 02:56:21
- Total runtime: 6979s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260622_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.1m)
  - Fixes:
    - 2026-06-22 01:00:04,670 INFO Committed 12 file(s).
- 2. ✗ Code Auditor (1.8m)
  - Problems:
    - 2026-06-22 01:01:52,857 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' re...
- 3. ✓ Dead Code Auditor (7.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (17.5m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.0m)
  - Problems:
    - Transcript review found 8 issues: 3 critical, 2 low, 3 medium.
    - Stage 1 emitted an out-of-schema intent label before falling back to others.
    - Stage 1 emitted another out-of-schema label, 'force stage3'.
  - Fixes:
    - 2026-06-22 01:29:25,901 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-06-22 01:29:25,902 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 3 medium, 2...
- 7. ✓ Memory Janitor (86.8m)
  - Problems:
    - untime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:34:57 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
    - [0;93m2026-06-22 02:39:23.651081519 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-22 02:39:23.651127379 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 16 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.1m)
  - Problems:
    - 2026-06-22 02:56:20,691 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address
  - Fixes:
    - 2026-06-22 02:56:20,429 INFO Committed 6 file(s).

**Top follow-ups:**

- Constrain intent_classifier.v3.classifier to a fixed enum with structured decoding, or add an alias map for model-only labels like 'web automation'.
- Add enum-constrained classifier output and reject or remap routing phrases before they become logged intent classes.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 3s (0.1 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-22 01:00:04,670 INFO Committed 12 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 108s (1.8 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-22 01:01:52,857 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 422s (7.0 min)

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
- Duration: 1051s (17.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

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
- Duration: 177s (3.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 3 critical, 2 low, 3 medium.
- Stage 1 emitted an out-of-schema intent label before falling back to others.
- Stage 1 emitted another out-of-schema label, 'force stage3'.
- Stage 3 lost multi-turn context for a follow-up instruction.
- Stage 1 classification latency was excessive for a short follow-up.

### Improvements It Made

- 2026-06-22 01:29:25,901 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-06-22 01:29:25,902 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 3 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain intent_classifier.v3.classifier to a fixed enum with structured decoding, or add an alias map for model-only labels like 'web automation'.
- Add enum-constrained classifier output and reject or remap routing phrases before they become logged intent classes.
- Fix jane.proxy or the Stage 3 adapter to load conversation history by sid audit-178201, and attach relevant file context when the conversation is about source-code inspection.
- Add a short classifier timeout, for example 1-2 seconds, and default to others escalation when the local classifier is slow.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 5210s (86.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- untime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:34:57 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-22 02:39:23.651081519 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-22 02:39:23.651127379 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-22 02:39:23.651142728 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-22 02:39:23.862140701 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-22 06:39:23 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 16 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 3s (0.1 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- 2026-06-22 02:56:20,691 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address

### Improvements It Made

- 2026-06-22 02:56:20,429 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
