# Most Recent Nightly Self-Improvement

- Run started: 2026-05-05 01:00:01
- Report generated: 2026-05-05 02:28:16
- Total runtime: 5294s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260505_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-05 01:00:02,477 INFO Committed 10 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-05-05 01:00:02,635 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (5.8m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (16.5m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 4.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.8m)
  - Problems:
    - Transcript review found 12 issues: 10 critical, 2 medium.
    - Stage 3 dropped the turn and returned no final response.
    - A follow-up reply was not routed by the pending-action resolver; it was treated as a fresh `others` request and then dropped.
  - Fixes:
    - 2026-05-05 01:26:15,639 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
    - 2026-05-05 01:26:15,640 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 10 critical, 2 medium is...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - [0;93m2026-05-05 01:57:08.637713729 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-05 01:57:08.637753305 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-05 01:57:08.637777233 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-05 02:26:16,311 INFO Committed 9 file(s).

**Top follow-ups:**

- In the Stage 3 proxy/escalation path, catch stream failures and always return a final error payload or retry result instead of allowing the stream to end without a response.
- Persist pending-action state from Stage 2/Stage 3 follow-up questions and route short affirmative/parameter-only replies directly to the owning handler before classification.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-05 01:00:02,477 INFO Committed 10 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-05 01:00:02,635 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 351s (5.8 min)

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

- Status: `ok`
- Duration: 991s (16.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 12.
- Classification failures: 4.
- Response failures: 7.
- **I want them to periodically get the lead after some time** (timer/stage3): Can you clarify what you mean? Who is "them" and what does "getting the lead" look like in this context — are you talking about the Stage 2/3 pipeline
- **yes those articles and maybe just two days** (others/stage3): I'm picking up from where we left off, but I've lost the earlier context. I know there was an open loop about clarifying "them" and "get the lead" — y
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Based on my research, here's what I found about sounds in the STT flow:
- **__debug_inspect_update_short_term_memory** (others/stage3): Here's the full picture of the short-term memory update system:

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

- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 230s (3.8 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 12 issues: 10 critical, 2 medium.
- Stage 3 dropped the turn and returned no final response.
- A follow-up reply was not routed by the pending-action resolver; it was treated as a fresh `others` request and then dropped.
- Stage 3 dropped the turn and returned no final response.
- Classifier prompt-injection misrouted the turn to `greeting`, the greeting handler returned an invalid shape, and the request then failed in Stage 3.

### Improvements It Made

- 2026-05-05 01:26:15,639 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
- 2026-05-05 01:26:15,640 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 10 critical, 2 medium issues. The most urgent was: Sta

### Follow-Up Fixes Recommended

- In the Stage 3 proxy/escalation path, catch stream failures and always return a final error payload or retry result instead of allowing the stream to end without a response.
- Persist pending-action state from Stage 2/Stage 3 follow-up questions and route short affirmative/parameter-only replies directly to the owning handler before classification.
- Add a guaranteed fallback response on Stage 3 stream failure and trip a temporary health gate after repeated `Brain execution failed (stream)` events.
- Strip or neutralize user-supplied protocol/XML blocks before classification, ignore literal class-contract text as intent evidence, and enforce handler response schemas with tests so invalid shapes cannot reach production.

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
- [0;93m2026-05-05 01:57:08.637713729 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-05 01:57:08.637753305 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-05 01:57:08.637777233 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:57:08 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-05 01:59:24.507424949 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:59:24 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-05 01:59:24.507471038 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-05 05:59:24 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-05-05 02:26:16,311 INFO Committed 9 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
