# Most Recent Nightly Self-Improvement

- Run started: 2026-04-19 01:00:01
- Report generated: 2026-04-19 01:39:11
- Total runtime: 2349s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260419_010001.md`

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

- 2026-04-19 01:00:02,110 INFO Committed 101 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Dead Code Auditor

- Status: `timeout`
- Duration: 900s (15.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Job ended with status `timeout`.
- Dead files — review needed: 10.
- Possibly-dead functions: 47.
- Duplicate function bodies: 21 groups.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 3: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-19 01:15:02,246 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 621s (10.3 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures.

### Problems It Found

- Prompts audited: 30.
- Classification failures: 21.
- Response failures: 26.
- **well that is a problem can you fix that** (error/stage2): Sorry, could you say that again?
- **I don't understand why there's a short circuit there should not be short circuit** (error/stage2): Sorry, could you say that again?
- **no we designed a three-stage specifically for this reason so we can capture erro** (error/stage2): Sorry, could you say that again?
- **<memory_verify priority="critical">

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

- CRON_JOBS.md missing entry for active cron script: daily_code_review.py
- CRON_JOBS.md missing entry for active cron script: fetch_todo_list.py
- CRON_JOBS.md missing entry for active cron script: fetch_weather.py
- CRON_JOBS.md missing entry for active cron script: run_briefing.py
- CRON_JOBS.md mentions ambient_heartbeat.py but no matching cron entry exists
- CRON_JOBS.md mentions audit_auto_fixer.py but no matching cron entry exists
- CRON_JOBS.md mentions auto_pull.sh but no matching cron entry exists
- CRON_JOBS.md mentions bot_watchdog.sh but no matching cron entry exists

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `exit-1`
- Duration: 824s (13.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced.

### Problems It Found

- Job ended with status `exit-1`.
- Transcript review found 20 issues: 4 critical, 1 low, 15 medium.
- Obvious time request was routed as a stale Stage 3 follow-up instead of going through Stage 1/Stage 2 get-time fast path.
- Air-quality weather request was classified correctly but Stage 2 rejected it and escalated to slow Stage 3.
- Greeting fast path was correct but too slow for a Stage 2 handler.
- Weather fast path was correct but took 7.5 seconds in Stage 2.

### Improvements It Made

- 2026-04-19 01:29:08,727 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (20 issues)
- 2026-04-19 01:29:08,728 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 15 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add a resolver pre-check for high-precision interrupt intents such as GET_TIME, WEATHER, TIMER, SMS, and CANCEL; if matched, clear or suspend the pending action and run normal Stage 1 classification.
- Extend the weather handler gate and handler implementation to support air-quality queries; do not self-correct valid class-labeled utterances into DELEGATE_OPUS until a reviewer or post-check verifies the class was actually wrong.
- Make greeting responses fully local and nonblocking; remove any memory, broadcast, or external calls from the greeting handler path and add a latency assertion for greetings under 500ms.
- Instrument the weather handler by sub-step, cache current weather reads briefly, and enforce a timeout/fallback response so Stage 2 weather does not block voice UX for multiple seconds.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- No problems were detected in the available logs/reports.

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

- 2026-04-19 01:39:10,053 INFO Committed 10 file(s).
- 2026-04-19 01:39:11,291 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
