# Most Recent Nightly Self-Improvement

- Run started: 2026-04-18 01:00:00
- Report generated: 2026-04-18 23:11:47
- Total runtime: 2824s
- Jobs: 8 total, 5 ok, 2 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260418_010000_2.md`

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-18 01:00:01,882 INFO Committed 22 file(s).

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

- 2026-04-18 01:15:02,004 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `timeout`
- Duration: 1200s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures.

### Problems It Found

- Job ended with status `timeout`.
- Prompts audited: 30.
- Classification failures: 0.
- Response failures: 2.
- **yes fix it** (others/stage3): Chieh, I'm not sure what you're referring to — could you give me a bit more context? What needs fixing?
- **hey Jane, i previously asked you to fix the security issues raised by codex, how** (others/stage3): Chieh, I looked through the job queue, audit reports, and configs, and I don't see a specific "security issues from Codex" task tracked anywhere. It's

### Improvements It Made

- 2026-04-18 01:33:13,275 [INFO] Added exemplar: 'please read the last 3 turns from Android Jane, the "how are' → GREETING (GREETING_audit_1776490392)
- 2026-04-18 01:33:13,275 [INFO] AUTO-FIX: added 'please read the last 3 turns from Android Jane, the "how are' to greeting (was: others)

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
- Duration: 722s (12.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced.

### Problems It Found

- Job ended with status `exit-1`.
- Transcript review found 17 issues: 6 critical, 1 low, 10 medium.
- Stage 3 took over two minutes to answer a follow-up and appears to have produced no accumulated response text.
- Weather fast path was classified correctly but was slow for a Stage 2 handler.
- Stage 3 gave an ungrounded/inaccurate answer about Google Docs capability.
- Stage 3 turn took nearly three minutes for an implementation request.

### Improvements It Made

- 2026-04-18 01:37:04,944 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (17 issues)
- 2026-04-18 01:37:04,945 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 6 critical, 10 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Fix standing_brain stream parsing so final result events are always surfaced even when accumulated streaming text is empty; add a timeout/fallback that returns the final result payload instead of an empty response.
- Profile the weather handler network/API path and add request timeouts plus cached recent weather for voice fast path; emit an immediate short acknowledgement only if the handler is expected to exceed a voice latency budget.
- Require Stage 3 capability answers to inspect registered tools/integrations before answering; add a Google Docs capability protocol that distinguishes read-only document access, API auth, and edit/write access.
- Separate implementation work from voice response: return a short confirmed plan quickly, then run code work asynchronously. Also fix stream accumulation when result events arrive without incremental text.

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

- 2026-04-18 01:47:06,255 INFO Committed 10 file(s).
- 2026-04-18 01:47:07,235 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
