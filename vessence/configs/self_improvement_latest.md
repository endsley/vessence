# Most Recent Nightly Self-Improvement

- Run started: 2026-05-10 01:00:02
- Report generated: 2026-05-10 02:37:00
- Total runtime: 5818s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260510_010002.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-10 01:00:03,972 INFO Committed 5 file(s).
- 2. ✓ Code Auditor (4.9m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.5m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 13.
    - Classification failures: 8.
    - Response failures: 13.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.5m)
  - Problems:
    - Transcript review found 6 issues: 2 critical, 4 medium.
    - Pending follow-up was not resolved; a contextual reply fragment went through normal classification
    - User-supplied protocol text was treated as a real `greeting` intent, and the greeting fast-path then failed schema validation
  - Fixes:
    - 2026-05-10 01:34:59,921 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-05-10 01:34:59,922 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 4 medium iss...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - [0;93m2026-05-10 01:55:56.604011163 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-10 01:55:56.604077370 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-10 01:55:56.604100586 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-10 02:35:00,678 INFO Committed 4 file(s).

**Top follow-ups:**

- Persist pending_action whenever Stage 2 or Stage 3 asks a follow-up question, run the resolver before classification on every turn, and add tests for short contextual answers like `yes ... two days`.
- Sanitize or neutralize control-looking markup before classification, classify from semantic intent rather than literal label mentions, and add contract tests that fail any handler response not matching the expected schema.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-10 01:00:03,972 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 293s (4.9 min)

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
- Duration: 391s (6.5 min)

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

- Status: `timeout`
- Duration: 1200s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Job ended with status `timeout`.
- Prompts audited: 13.
- Classification failures: 8.
- Response failures: 13.
- **I want them to periodically get the lead after some time** (timer/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)

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
- Duration: 210s (3.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 2 critical, 4 medium.
- Pending follow-up was not resolved; a contextual reply fragment went through normal classification
- User-supplied protocol text was treated as a real `greeting` intent, and the greeting fast-path then failed schema validation
- Short-term-memory introspection was degraded because the extractor was failing on every turn
- A codebase-inspection request reached Stage 3 without any file context even though the user gave an explicit path

### Improvements It Made

- 2026-05-10 01:34:59,921 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-05-10 01:34:59,922 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 4 medium issues. The most urgent was: Pend

### Follow-Up Fixes Recommended

- Persist pending_action whenever Stage 2 or Stage 3 asks a follow-up question, run the resolver before classification on every turn, and add tests for short contextual answers like `yes ... two days`.
- Sanitize or neutralize control-looking markup before classification, classify from semantic intent rather than literal label mentions, and add contract tests that fail any handler response not matching the expected schema.
- Take the remote LLM extractor out of the hot path or add a local fallback, add a circuit breaker after repeated failures, and expose a degraded-memory status to Stage 3 so it does not imply live memory inspection succeeded.
- Expand `~` before path parsing, detect filesystem paths in utterances, and auto-attach repo or file context before escalating code-inspection requests to Stage 3.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 3600s (60.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- [0;93m2026-05-10 01:55:56.604011163 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-10 01:55:56.604077370 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-10 01:55:56.604100586 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:56 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-10 01:55:57.355851561 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:57 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-10 01:55:57.355935768 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-10 05:55:57 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `timeout`
- Duration: 120s (2.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- Job ended with status `timeout`.

### Improvements It Made

- 2026-05-10 02:35:00,678 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
