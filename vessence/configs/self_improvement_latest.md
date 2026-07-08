# Most Recent Nightly Self-Improvement

- Run started: 2026-07-07 01:00:01
- Report generated: 2026-07-07 03:02:40
- Total runtime: 7358s
- Jobs: 8 total, 5 ok, 2 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260707_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-07 01:00:03,871 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (3.3m)
  - Problems:
    - 2026-07-07 01:03:21,993 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verif...
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
- 6. ✓ Transcript Quality Review (0.8m)
  - Problems:
    - Transcript review found 5 issues: 1 critical, 2 low, 2 medium.
    - Classifier emitted an unsupported intent label before falling back to others.
    - Stage 1 classification was extremely slow for a request that only needed Stage 3 escalation.
  - Fixes:
    - 2026-07-07 01:39:08,089 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-07-07 01:39:08,098 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 2...
- 7. ✓ Memory Janitor (83.5m)
  - Problems:
    - [0;93m2026-07-07 02:38:35.600551302 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-07 02:38:35.600595745 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-07 02:38:35.600607211 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-07 03:02:38,251 INFO Committed 5 file(s).
    - 2026-07-07 03:02:40,404 INFO Pushed successfully.

**Top follow-ups:**

- Constrain Stage 1 output to the configured intent enum, or add explicit normalization for known meta labels like `force stage3` before logging them as unknown.
- Add a short classifier timeout and fail-open to `others:Low` for complex/freeform requests, then run memory extraction asynchronously so Stage 1 latency is not tied to slow local LLM calls.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-07 01:00:03,871 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 198s (3.3 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-07-07 01:03:21,993 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

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
- Duration: 45s (0.8 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 1 critical, 2 low, 2 medium.
- Classifier emitted an unsupported intent label before falling back to others.
- Stage 1 classification was extremely slow for a request that only needed Stage 3 escalation.
- Classifier emitted another unsupported intent label before falling back to others.
- Stage 3 took over nine minutes to complete a coding request.

### Improvements It Made

- 2026-07-07 01:39:08,089 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-07-07 01:39:08,098 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain Stage 1 output to the configured intent enum, or add explicit normalization for known meta labels like `force stage3` before logging them as unknown.
- Add a short classifier timeout and fail-open to `others:Low` for complex/freeform requests, then run memory extraction asynchronously so Stage 1 latency is not tied to slow local LLM calls.
- Update the Stage 1 prompt/schema to reject non-enum labels, or map `web automation` to `others` without warning when the request is a coding/project task.
- Separate Stage 3 execution from memory extraction/fallback LLM work, enforce per-subtask timeouts, and surface progress heartbeats so long coding tasks do not appear stalled.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 5009s (83.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-07-07 02:38:35.600551302 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-07 02:38:35.600595745 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-07 02:38:35.600607211 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-07 02:38:35.769077215 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-07 02:38:35.769117177 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-07 06:38:35 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-07-07 03:02:38,251 INFO Committed 5 file(s).
- 2026-07-07 03:02:40,404 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
