# Most Recent Nightly Self-Improvement

- Run started: 2026-07-12 23:30:01
- Report generated: 2026-07-12 23:49:28
- Total runtime: 1166s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260712_233001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-12 23:30:01,694 INFO Committed 10 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems: none detected
  - Fixes: none applied
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 11 groups.
- 4. ✓ Pipeline Audit (30 prompts) (3.5m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 4.
    - Response failures: 6.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims check_for_updates.py is active but no matching cron entry exists
    - CRON_JOBS.md claims generate_code_map.py is active but no matching cron entry exists
    - CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- 6. ✓ Transcript Quality Review (0.9m)
  - Problems:
    - Transcript review found 5 issues: 3 critical, 1 low, 1 medium.
    - Stage 3 did not complete the requested project-familiarization turn.
    - Stage 1 reported an unknown class from the classifier.
  - Fixes:
    - 2026-07-12 23:49:25,000 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-07-12 23:49:25,001 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium, 1...
- 7. ✓ Memory Janitor (0.0m)
  - Problems:
    - WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 37.2% > 10.0%
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-12 23:49:27,882 INFO Pushed successfully.

**Top follow-ups:**

- Add a bounded Stage 3 execution timeout with a resumable background-task path: return an immediate status response, keep the Codex/brain task running server-side when appropriate, and expose completion/progress instead of cancelling on client stream disconnect.
- Constrain classifier output to the canonical enum with strict JSON/schema validation, and add a classifier normalization/test case for source-code inspection requests so invalid labels like 'force stage3' cannot be emitted.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 4 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-12 23:30:01,694 INFO Committed 10 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

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

- Status: `ok`
- Duration: 207s (3.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 4.
- Response failures: 6.
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **use the source code as your guide** (todo list/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **please familiarize yourself with the waterlily project** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit

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

- CRON_JOBS.md claims check_for_updates.py is active but no matching cron entry exists
- CRON_JOBS.md claims generate_code_map.py is active but no matching cron entry exists
- CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- CRON_JOBS.md claims notify_updates.py is active but no matching cron entry exists
- CRON_JOBS.md claims usb_sync.py is active but no matching cron entry exists

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 56s (0.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 3 critical, 1 low, 1 medium.
- Stage 3 did not complete the requested project-familiarization turn.
- Stage 1 reported an unknown class from the classifier.
- Stage 3 returned an implausibly short response for a large code-modification request.
- Stage 3 did not actually self-heal the Android crash report.

### Improvements It Made

- 2026-07-12 23:49:25,000 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-07-12 23:49:25,001 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 1 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add a bounded Stage 3 execution timeout with a resumable background-task path: return an immediate status response, keep the Codex/brain task running server-side when appropriate, and expose completion/progress instead of cancelling on client stream disconnect.
- Constrain classifier output to the canonical enum with strict JSON/schema validation, and add a classifier normalization/test case for source-code inspection requests so invalid labels like 'force stage3' cannot be emitted.
- Treat provider spend-limit errors as a hard degraded-state signal for Stage 3 coding tasks; do not return a generic 99-character completion. Route to a configured working fallback brain with tools, or return a clear failure/status response.
- Add health checks before accepting self-heal/coding tasks: verify the configured Stage 3 provider and fallback can run with tools. If unavailable, fail fast with an actionable error instead of producing a tiny generic answer.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 37.2% > 10.0%

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-12 23:49:27,882 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
