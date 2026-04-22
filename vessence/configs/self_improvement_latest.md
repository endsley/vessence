# Most Recent Nightly Self-Improvement

- Run started: 2026-04-21 01:00:01
- Report generated: 2026-04-21 01:38:16
- Total runtime: 2294s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260421_010001.md`

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 116s (1.9 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-21 01:01:58,297 INFO Committed 88 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Dead Code Auditor

- Status: `ok`
- Duration: 891s (14.8 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Dead files — review needed: 40.
- Possibly-dead functions: 35.
- Duplicate function bodies: 9 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 40 flagged, 35 dead funcs, 9 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 3: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-21 01:16:49,561 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 531s (8.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures.

### Problems It Found

- Prompts audited: 30.
- Classification failures: 7.
- Response failures: 18.
- **who's coming in tomorrow** (clinic schedules info/stage2): On Wednesday she has 8 active patients: John Meeks, Mock Patient, Prabitha Natarajan, Suprama Datta, and 4 more. Cancelled: Prabitha Natarajan, Meliss
- **how about tomorrow** (clinic schedules info/stage2): She has 8 active patients on Wednesday, with 2 cancellations (10 total booked). Would you like to know about another day?
- **casual look like tomorrow** (weather/stage3): Tomorrow she has 10 slots on the books. Two are cancelled — Melissa Solomon at 8 AM and Prabitha Natarajan at 11. That leaves 8 active patients, start
- **what does my schedule look like tomorrow** (others/stage3): Your calendar is clear tomorrow — nothing scheduled for Wednesday.

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

- CRON_JOBS.md missing entry for active cron script: run_briefing.py
- CRON_JOBS.md mentions bot_watchdog.sh but no matching cron entry exists
- CRON_JOBS.md mentions prompt_queue_runner.py but no matching cron entry exists
- SKILLS_REGISTRY.md references missing file: agent_skills/gemma_query.py

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 634s (10.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced.

### Problems It Found

- Transcript review found 18 issues: 5 critical, 1 low, 12 medium.
- SMS confirmation attempted to send with no open draft.
- Direct SMS request missed the Stage 2 send-message fast path.
- Clinic schedule request was routed to Stage 3 instead of the clinic schedule handler.
- Clinic-style schedule query was classified as read calendar, which has no Stage 2 handler.

### Improvements It Made

- 2026-04-21 01:28:37,653 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (18 issues)
- 2026-04-21 01:28:37,654 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 5 critical, 12 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Make SMS confirmation state authoritative: first turn must emit contacts.sms_draft with a stable draft_id, pending_action_resolver must route 'yes send it' to sms_send for that draft_id, and sms_send should never be emitted without an existing draft.
- Add classifier examples and deterministic pre-rules for 'tell/contact my wife/husband/spouse' as send message, including family aliases.
- Canonicalize classifier labels by stripping brackets, underscores, and case/spacing variants before validation.
- Route provider/patient schedule phrasing in clinic test sessions to clinic schedules info, or implement a read calendar handler instead of always escalating.

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

- Status: `timeout`
- Duration: 120s (2.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- Job ended with status `timeout`.

### Improvements It Made

- 2026-04-21 01:36:16,751 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
