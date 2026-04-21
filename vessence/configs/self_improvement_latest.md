# Most Recent Nightly Self-Improvement

- Run started: 2026-04-20 01:00:01
- Report generated: 2026-04-20 01:19:41
- Total runtime: 1178s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260420_010001.md`

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

- 2026-04-20 01:00:02,636 INFO Committed 120 file(s).

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

- 2026-04-20 01:15:02,759 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 269s (4.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures.

### Problems It Found

- Prompts audited: 13.
- Classification failures: 6.
- Response failures: 8.
- **<jane_architecture>
- **<jane_architecture>
- **<memory_verify priority="critical">
- **<jane_architecture>

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

- Status: `ok`
- Duration: 3s (0.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-20 01:19:35,986 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-04-20 01:19:35,987 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

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
- Duration: 3s (0.1 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-20 01:19:40,767 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
