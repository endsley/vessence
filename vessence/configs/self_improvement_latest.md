# Most Recent Nightly Self-Improvement

- Run started: 2026-05-19 01:00:01
- Report generated: 2026-05-19 01:41:25
- Total runtime: 2484s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260519_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-19 01:00:02,007 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (6.8m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.4m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 1.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 8 issues: 4 critical, 4 medium.
    - Follow-up reply was not routed through pending_action_resolver and lost prior-turn context.
    - Stage 3 response path was extremely slow for a simple explanatory question.
  - Fixes:
    - 2026-05-19 01:35:22,096 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-05-19 01:35:22,097 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 4 medium iss...
- 7. ✓ Memory Janitor (4.0m)
  - Problems:
    - WARNING:system_load:System still busy after 5 min — giving up.
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-19 01:39:25,944 INFO Committed 5 file(s).

**Top follow-ups:**

- Persist pending_action by session_id before assistant follow-up is emitted, and have pending_action_resolver log both hits and misses before Stage 1. Add a regression test where 'yes ... two days' bypasses classification.
- Respawn the standing brain once when vault state changes and reuse it across turns; move short_term_extractor off the synchronous critical path or enforce a shorter nonblocking timeout.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-19 01:00:02,007 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 408s (6.8 min)

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
- Duration: 442s (7.4 min)

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
- Duration: 1199s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 1.
- Response failures: 3.
- **yes those articles and maybe just two days** (others/stage3): I don't have context from the previous conversation — what articles are you referring to, and what's the two-day timeframe for? Give me a quick recap
- **currently how does your short-term memory work** (others/stage3): Here's how short-term memory works right now:
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Here's what I see:

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
- Duration: 69s (1.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 4 critical, 4 medium.
- Follow-up reply was not routed through pending_action_resolver and lost prior-turn context.
- Stage 3 response path was extremely slow for a simple explanatory question.
- Prompt-injection-like user text caused Stage 1 to misclassify the turn as greeting and load the greeting class protocol.
- Diagnostics request took over three minutes and had no Android diagnostic evidence available.

### Improvements It Made

- 2026-05-19 01:35:22,096 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-05-19 01:35:22,097 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 4 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action by session_id before assistant follow-up is emitted, and have pending_action_resolver log both hits and misses before Stage 1. Add a regression test where 'yes ... two days' bypasses classification.
- Respawn the standing brain once when vault state changes and reuse it across turns; move short_term_extractor off the synchronous critical path or enforce a shorter nonblocking timeout.
- Treat class_protocol blocks in user input as inert text before classification, add injection examples to the classifier eval set, and validate handler return schemas in unit tests.
- Attach recent Android diagnostic events to Stage 3 context for voice/audio bug reports, or add a deterministic diagnostics handler that queries voice_flow and tool_handler logs directly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 243s (4.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:system_load:System still busy after 5 min — giving up.

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

- 2026-05-19 01:39:25,944 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
