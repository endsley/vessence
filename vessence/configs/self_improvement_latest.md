# Most Recent Nightly Self-Improvement

- Run started: 2026-05-18 01:00:01
- Report generated: 2026-05-18 01:34:46
- Total runtime: 2084s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260518_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-18 01:00:01,880 INFO Committed 2 file(s).
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
- 4. ✓ Pipeline Audit (30 prompts) (15.8m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 3.
    - Response failures: 5.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.4m)
  - Problems:
    - Transcript review found 12 issues: 7 critical, 5 medium.
    - Follow-up reply was not routed through pending_action_resolver
    - Stage 3 rate-limit output appears to have been treated as a successful assistant response
  - Fixes:
    - 2026-05-18 01:28:43,738 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
    - 2026-05-18 01:28:43,739 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 7 critical, 5 medium iss...
- 7. ✓ Memory Janitor (4.0m)
  - Problems:
    - WARNING:system_load:System still busy after 5 min — giving up.
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-18 01:32:46,682 INFO Committed 5 file(s).

**Top follow-ups:**

- Persist pending_action state by session and add an explicit pre-Stage-1 resolver log for every turn showing pending_action_found=true/false. If pending_action exists, bypass Stage 1 and call the owning handler.
- Detect known Claude CLI failure strings in standing_brain output and return a structured provider_error instead of streaming it as Jane's answer. Add fallback to another model or a clear user-facing outage message.

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

- 2026-05-18 01:00:01,880 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 294s (4.9 min)

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

- Status: `ok`
- Duration: 945s (15.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 3.
- Response failures: 5.
- **yes those articles and maybe just two days** (others/stage3): I don't have context from what came before — looks like this is continuing a prior conversation that I can't see. What articles are you referring to,
- **currently how does your short-term memory work** (others/stage3): Here's how short-term memory works right now:
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Based on the code, there are two different situations depending on whether you're talking about **Android** or **web**:
- **can you look at the short-term memory to see if this whole thing is actually bei** (others/stage3): Here's the full diagnosis:

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
- Duration: 87s (1.4 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 12 issues: 7 critical, 5 medium.
- Follow-up reply was not routed through pending_action_resolver
- Stage 3 rate-limit output appears to have been treated as a successful assistant response
- Memory-sensitive question was sent to Stage 3 without usable memory context
- Stage 3 rate-limit output appears to have been treated as a successful assistant response

### Improvements It Made

- 2026-05-18 01:28:43,738 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
- 2026-05-18 01:28:43,739 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 7 critical, 5 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action state by session and add an explicit pre-Stage-1 resolver log for every turn showing pending_action_found=true/false. If pending_action exists, bypass Stage 1 and call the owning handler.
- Detect known Claude CLI failure strings in standing_brain output and return a structured provider_error instead of streaming it as Jane's answer. Add fallback to another model or a clear user-facing outage message.
- Before Stage 3, detect memory/meta-memory questions and inject current short-term-memory state from the memory store. Do not depend on the post-turn extractor for answering the current turn.
- Make standing_brain classify provider limit messages as failures and prevent them from being delivered as normal assistant text.

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

- 2026-05-18 01:32:46,682 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
