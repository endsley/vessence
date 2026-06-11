# Memory Verification Report — 2026-06-11 02:32

Checked: 20 | Stale: 10 | Fixed: 10 | Deleted: 0 | Errors: 0 | Skipped recent: 184

- **UPDATED** `49bad57a-91c` — Confirmed from git status/log plus backend/main.py, backend/events.py, backend/bookings.py, backend/space_requests.py, frontend local-assets, and docs; the old memory's git state is stale but the dirty-worktree and feature-status claims are mostly right.
- **UPDATED** `5193e292-84c` — Confirmed in backend/accounting.py and backend/main.py: package rows are extracted from service-sales detail rows by numeric invoice id; matched rows set amount from amount_charged, adjusted from amount_adjusted, paid/square_matched/package_matched from amount_received, balance to $0.00, and admin review marks package rows verified.
- **UPDATED** `df38bd7a-069` — Codex was right: the code sets row['amount'] from amount_charged and row['adjusted'] from amount_adjusted, while paid/package_matched/package_amount_received use amount_received.
- **UPDATED** `543316d6-a0f` — Confirmed against the actual backup script, crontab, mounted USB, backup log, restore doc, and current manifest. Codex was right substantively; the original memory is partial because it is truncated at 'paym'.
- **UPDATED** `e694cdbb-549` — Confirmed from actual auth.js and HTML references; Codex was right that the old memory was partially stale.
- **UPDATED** `0f348850-0a8` — Read the migrations, app/main.py, app/services/prompts.py, app/routers/admin.py, app/problems/base.py, and problem/test examples. Codex was right: the old memory was truncated and omitted the current source-signature stale-row behavior, while the substantive existing claims still match current code.
- **UPDATED** `6915f2e4-e10` — Codex was right: the core service/project/app claims are confirmed, but the memory was incomplete and needed the deploy-script/runbook caveat plus the exam-script confirmation.
- **UPDATED** `f4352c11-da8` — Verified against the actual repo: app/main.py defines FastAPI, repo docs/scripts reference classes.chiehwu.com, the Vessence auditor still targets localhost:8501/dev-login and Cloud SQL proxy settings, git HEAD/status match Codex's verdict, and alembic heads reports 0077_section_event_border_color.
- **UPDATED** `d41c8d92-a17` — Confirmed against teacher.py, deps.py, and templates. Codex was right: the original memory is truncated and overstates TA unenrollment support.
- **UPDATED** `4b55a956-525` — Codex was mostly right: the original quarantine path was truncated, short-term janitor deletes still bypass quarantine, and current live cron runs via nightly_self_improve; actual code also shows setup.sh still has a standalone janitor cron template.
