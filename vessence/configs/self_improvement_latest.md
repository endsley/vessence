# Most Recent Nightly Self-Improvement

- Run started: 2026-07-06 01:00:01
- Report generated: 2026-07-06 02:56:44
- Total runtime: 7001s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260706_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-06 01:00:03,990 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (4.0m)
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
- 6. ✓ Transcript Quality Review (2.5m)
  - Problems:
    - Transcript review found 6 issues: 1 critical, 2 low, 3 medium.
    - Stage 1 emitted an unsupported class before falling back to others.
    - The follow-up was sent to Stage 3 without prior conversation or source context.
  - Fixes:
    - 2026-07-06 01:41:36,076 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-07-06 01:41:36,085 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 2...
- 7. ✓ Memory Janitor (75.1m)
  - Problems:
    - [0;93m2026-07-06 02:16:08.255849916 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-06 02:16:08.255895037 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-06 02:16:08.255907003 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-06 02:56:43,550 INFO Pushed successfully.

**Top follow-ups:**

- Constrain Stage 1 to the allowed enum with structured decoding, or explicitly normalize stage3-forcing aliases before logging and metrics.
- Persist and pass conversation history for `sid_override` sessions, and attach repo/source context or route to a code-aware Stage 3 path when the user asks to use source code.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-06 01:00:03,990 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 239s (4.0 min)

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
- Duration: 151s (2.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 1 critical, 2 low, 3 medium.
- Stage 1 emitted an unsupported class before falling back to others.
- The follow-up was sent to Stage 3 without prior conversation or source context.
- Stage 1 classification latency was extremely high.
- Project familiarization was invoked without visible project/source context.

### Improvements It Made

- 2026-07-06 01:41:36,076 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-07-06 01:41:36,085 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain Stage 1 to the allowed enum with structured decoding, or explicitly normalize stage3-forcing aliases before logging and metrics.
- Persist and pass conversation history for `sid_override` sessions, and attach repo/source context or route to a code-aware Stage 3 path when the user asks to use source code.
- Add a hard timeout around Stage 1, fall back to `others:Low` within a small latency budget, and investigate the classifier backend stall.
- For project-specific requests, route Stage 3 through the local code-agent path or attach indexed repo context before generation.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4505s (75.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-07-06 02:16:08.255849916 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-06 02:16:08.255895037 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-06 02:16:08.255907003 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-06 02:16:08.410494808 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-06 02:16:08.410552002 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-06 06:16:08 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-07-06 02:56:43,550 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
