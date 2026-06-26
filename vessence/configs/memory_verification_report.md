# Memory Verification Report — 2026-06-26 03:16

Checked: 20 | Stale: 11 | Fixed: 11 | Deleted: 0 | Errors: 0 | Skipped recent: 227

- **UPDATED** `63267595-de0` — Confirmed in agent_skills/edu_homework_audit.py: Codex was right; the existing memory is truncated at the start-attempt endpoint and should be completed with the current /courses/{section_id}/hw/{assignment_id}/start flow and mode behavior.
- **UPDATED** `89e50333-91d` — Confirmed from current chieh_class_v2 code: the memory is mostly right, but variable parsing lives in app/services/custom_problems.py, not app/routers/teacher.py; current template solution handling also includes a python solution_kind path.
- **UPDATED** `356f64bf-c3f` — Codex was right that the memory is partially stale because it is truncated; verified against current models, curriculum service, and Alembic 0004/0006/0009/0010.
- **UPDATED** `acccce19-73d` — Verified against the migrations, models, prompt service, startup path, router/service call sites, and problem modules. Codex was right that the old memory is historically accurate but stale because drift detection now uses prompts.source_template_hash/source_module_version and source prompt templates remain active as signatures/fallbacks.
- **UPDATED** `c1dbedad-73e` — Code confirms the cache/new architecture and no saved-report TTL. The 2026-06-10 waterlily-auth.service restart claim was not evidenced by source, journal, or log files, so it should be removed.
- **UPDATED** `5193e292-84c` — Codex was right: the current code confirms the architecture and fields, but the stored memory is truncated and omits preserved invoice fields plus later package-purchase verification context.
- **UPDATED** `df38bd7a-069` — Current accounting.py confirms the package-service extraction and invoice_id matching behavior. Current main.py requires _income_package_purchase_square_verified before automatic package verification, so the old blanket admin-UI verified claim is stale.
- **UPDATED** `543316d6-a0f` — Read the backup script, live crontab, saved crontab backup, logs, mount state, and path existence. Codex was right: the stale part was the old /home/chieh/payment_reports, /home/chieh/payment_report_downloader.py, and /home/chieh/payment_report_rows.csv paths; the current preserved payment-report paths are inside /home/chieh/code/waterlily.
- **UPDATED** `e694cdbb-549` — Actual auth.js and HTML references confirm Codex was right: the memory's mount()/api/me behavior and old version-reference claims are stale, while the path and unused Google SVG detail remain accurate.
- **UPDATED** `0f348850-0a8` — Actual code confirms the prompt-store path and migrations, but the stored memory is truncated and needs the source-template fallback/stale-signature nuance.
- **UPDATED** `f4352c11-da8` — Verified against README.md, app/main.py, edu_homework_audit.py, git status, current git log, and merge-base checks; Codex was right that the old dirty-worktree and HEAD claims were stale.
