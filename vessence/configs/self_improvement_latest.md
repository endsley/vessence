# Most Recent Nightly Self-Improvement

- Run started: 2026-05-06 01:00:01
- Report generated: 2026-05-06 02:32:14
- Total runtime: 5531s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260506_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-06 01:00:02,231 INFO Committed 14 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-05-06 01:00:02,453 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (5.9m)
  - Problems:
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 4.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (4.2m)
  - Problems:
    - Transcript review found 6 issues: 2 critical, 4 medium.
    - Follow-up reply was treated as a brand-new request instead of resolving prior context.
    - User-supplied control text hijacked routing: Stage 1 treated the payload as a real `greeting` intent, and the greeting handler then failed.
  - Fixes:
    - 2026-05-06 01:30:12,904 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-05-06 01:30:12,905 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 4 medium iss...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - rrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
    - [0;93m2026-05-06 02:04:53.180816808 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-06 02:04:53.180856330 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-06 02:30:16,766 INFO Committed 4 file(s).

**Top follow-ups:**

- When Stage 2 or Stage 3 asks a clarifying question, persist a structured `pending_action` with the owning handler/brain and have `pending_action_resolver` consume short replies like `yes ...` before classification.
- Sanitize or strongly down-rank XML/control-token patterns before intent classification, and never load a handler protocol from user-supplied text. Add a schema-safe fallback when a handler receives malformed input.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-06 01:00:02,231 INFO Committed 14 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-06 01:00:02,453 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 355s (5.9 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups

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
- Duration: 254s (4.2 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 2 critical, 4 medium.
- Follow-up reply was treated as a brand-new request instead of resolving prior context.
- User-supplied control text hijacked routing: Stage 1 treated the payload as a real `greeting` intent, and the greeting handler then failed.
- A live voice-troubleshooting turn incurred unusable Stage 3 latency.
- Stage 1 emitted an unregistered label (`restart server`) for a website-debugging request and had to fall back to `others`.

### Improvements It Made

- 2026-05-06 01:30:12,904 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-05-06 01:30:12,905 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 4 medium issues. The most urgent was: User

### Follow-Up Fixes Recommended

- When Stage 2 or Stage 3 asks a clarifying question, persist a structured `pending_action` with the owning handler/brain and have `pending_action_resolver` consume short replies like `yes ...` before classification.
- Sanitize or strongly down-rank XML/control-token patterns before intent classification, and never load a handler protocol from user-supplied text. Add a schema-safe fallback when a handler receives malformed input.
- Keep the standing brain warm and unlocked across turns. If teardown fails, recreate the session asynchronously before the next user request instead of cold-restarting during the request path.
- Constrain classifier decoding to the registered intent enum, or post-validate and re-prompt the classifier when it returns an unknown label instead of silently mapping arbitrary labels to `others`.

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
- rrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-06 02:04:53.180816808 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-06 02:04:53.180856330 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-06 02:04:53.393960905 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-06 02:04:53.393998411 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-06 06:04:53 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-05-06 02:30:16,766 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
