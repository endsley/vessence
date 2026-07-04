# Most Recent Nightly Self-Improvement

- Run started: 2026-07-03 01:00:01
- Report generated: 2026-07-03 02:21:51
- Total runtime: 4909s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260703_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-03 01:00:02,985 INFO Committed 629 file(s).
- 2. ✓ Code Auditor (11.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 11 groups.
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- 6. ✓ Transcript Quality Review (4.1m)
  - Problems:
    - Transcript review found 5 issues: 1 critical, 2 low, 2 medium.
    - Stage 1 emitted an unsupported classifier label before falling back to Stage 3
    - Stage 1 was slow and rejected a class label because of space/underscore normalization
  - Fixes:
    - 2026-07-03 01:50:18,890 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-07-03 01:50:18,897 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 2...
- 7. ✓ Memory Janitor (31.5m)
  - Problems:
    - [0;93m2026-07-03 01:59:16.909958166 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-03 01:59:16.910012764 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-03 01:59:16.910042063 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 5 stale memories out of 9 checked. Stale memories make Jan...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-03 02:21:51,095 INFO Pushed successfully.

**Top follow-ups:**

- In intent_classifier/v3/classifier.py, canonicalize aliases such as 'force stage3', 'delegate opus', and 'DELEGATE_OPUS' before registry validation, then add a regression test for explicit Stage 3/meta requests.
- Normalize class IDs consistently in intent_classifier/v3/classifier.py by treating spaces and underscores equivalently, or separate display labels from canonical IDs. Add a fast bypass for long code/project prompts that should obviously go to Stage 3.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-03 01:00:02,985 INFO Committed 629 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 666s (11.1 min)

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

- Status: `timeout`
- Duration: 900s (15.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Job ended with status `timeout`.
- Possibly-dead functions: 1.
- Duplicate function bodies: 11 groups.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

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
- Duration: 0s (0.0 min)

### What It Did

- Compared source-of-truth docs against live cron, class, and file state to catch stale documentation.

### Problems It Found

- CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 248s (4.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 1 critical, 2 low, 2 medium.
- Stage 1 emitted an unsupported classifier label before falling back to Stage 3
- Stage 1 was slow and rejected a class label because of space/underscore normalization
- Short-term memory extraction failed during the Stage 3 workflow
- Stage 1 added a 23.1s delay before obvious Stage 3 escalation

### Improvements It Made

- 2026-07-03 01:50:18,890 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-07-03 01:50:18,897 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- In intent_classifier/v3/classifier.py, canonicalize aliases such as 'force stage3', 'delegate opus', and 'DELEGATE_OPUS' before registry validation, then add a regression test for explicit Stage 3/meta requests.
- Normalize class IDs consistently in intent_classifier/v3/classifier.py by treating spaces and underscores equivalently, or separate display labels from canonical IDs. Add a fast bypass for long code/project prompts that should obviously go to Stage 3.
- Make memory/v1/short_term_extractor.py use the configured available brain/provider, or health-check CLI providers at startup and disable unavailable fallbacks instead of retrying timed-out/auth-broken CLIs.
- In jane_web/jane_v3/pipeline.py, directly route long markdown/log/crash-report/code-edit prompts to Stage 3 before v3_classifier.classify, and keep qwen classification for short actionable voice intents.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 1889s (31.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-07-03 01:59:16.909958166 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-03 01:59:16.910012764 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-03 01:59:16.910042063 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:16 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-03 01:59:17.187079538 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:17 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-03 01:59:17.187114117 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-03 05:59:17 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 5 stale memories out of 9 checked. Stale memories make Jane give wrong answers about her own a

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

- 2026-07-03 02:21:51,095 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
