# Most Recent Nightly Self-Improvement

- Run started: 2026-05-16 01:00:01
- Report generated: 2026-05-16 01:37:16
- Total runtime: 2234s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260516_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-16 01:00:02,065 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (3.5m)
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
    - Prompts audited: 12.
    - Classification failures: 7.
    - Response failures: 12.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 8 issues: 3 critical, 5 medium.
    - Follow-up reply was not routed through pending_action_resolver and instead went through Stage 1/Stage 3
    - Stage 3 response path was extremely slow for a normal explanatory question
  - Fixes:
    - 2026-05-16 01:31:14,134 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-05-16 01:31:14,135 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 5 medium iss...
- 7. ✓ Memory Janitor (4.0m)
  - Problems:
    - WARNING:system_load:System still busy after 5 min — giving up.
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-16 01:35:16,502 INFO Committed 4 file(s).

**Top follow-ups:**

- Persist pending_action state across turns and add explicit resolver logging for both hit and miss cases. Before Stage 1, check pending_action for the session and route short confirmation/edit replies directly to the owning handler.
- Avoid per-turn brain restarts after vault unlock by respawning once and reusing the unlocked process. Move short_term_extractor work fully out of the response critical path or hard-cap it with a shorter nonblocking timeout.

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

- 2026-05-16 01:00:02,065 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 207s (3.5 min)

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
- Duration: 393s (6.5 min)

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
- Prompts audited: 12.
- Classification failures: 7.
- Response failures: 12.
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 10pm (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 10pm (America/New_York)

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/pipeline_audit_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_pipeline_audit_100.log

## Stage 5: Doc Drift Auditor

- Status: `ok`
- Duration: 1s (0.0 min)

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

- Transcript review found 8 issues: 3 critical, 5 medium.
- Follow-up reply was not routed through pending_action_resolver and instead went through Stage 1/Stage 3
- Stage 3 response path was extremely slow for a normal explanatory question
- Prompt-injection-like class_protocol text was classified as greeting with Very High confidence
- Greeting handler returned an invalid response shape

### Improvements It Made

- 2026-05-16 01:31:14,134 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-05-16 01:31:14,135 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 5 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action state across turns and add explicit resolver logging for both hit and miss cases. Before Stage 1, check pending_action for the session and route short confirmation/edit replies directly to the owning handler.
- Avoid per-turn brain restarts after vault unlock by respawning once and reusing the unlocked process. Move short_term_extractor work fully out of the response critical path or hard-cap it with a shorter nonblocking timeout.
- Sanitize user text before classification by stripping or escaping internal protocol tags. Add classifier tests for user-supplied '<class_protocol>' payloads and reject handler routing based on embedded protocol markup.
- Fix the greeting handler to always return the registered Stage 2 response schema. Add schema validation tests for every deterministic handler and fail closed with a clear internal error instead of silently escalating malformed handler output.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 242s (4.0 min)

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

- 2026-05-16 01:35:16,502 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
