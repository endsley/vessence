# Memory Verification Report — 2026-06-10 02:39

Checked: 20 | Stale: 13 | Fixed: 13 | Deleted: 0 | Errors: 0 | Skipped recent: 186

- **UPDATED** `9b95533c-bf0` — Confirmed in the skill, script, and backend accounting.py; the old memory is stale because output is now three TSV sections plus a merged TSV file, not just attended and canceled tables.
- **UPDATED** `2bca4180-d4d` — Confirmed in admin.html: summaryColumns are Date, Patient, Method, Amount/Paid/Balance, Verify; detailColumns contain Time, Service, Dur, Room, Invoice ID, Last Modified, with comment and conditional verification metadata in the disclosure.
- **UPDATED** `f61641c4-547` — Codex was right: the backend behavior still exists, but the original memory is truncated and stale about the UI label; use_existing_exports also does not auto-generate a missing match report.
- **UPDATED** `b7c370b1-fce` — Confirmed against auto_pull.sh, live crontab, crontab_backup, doc_drift_report.md, CRON_JOBS.md, news_fetcher.py, git ls-files, and git object store size. Codex was mostly right, but the live crontab is readable here and the old memory was truncated/incomplete.
- **UPDATED** `63267595-de0` — Confirmed against agent_skills/edu_homework_audit.py: Codex was right that the old memory is truncated and missing current attempt reuse/deletion behavior.
- **UPDATED** `ccff8811-02e` — Confirmed from the actual chieh_class_v2 code and registry output; the original memory is stale because its final matrix_operations claim is truncated/incomplete, while that topic now registers 42 keys.
- **UPDATED** `356f64bf-c3f` — Verified against current models, curriculum service, and alembic 0004/0009/0010; Codex was right that the stored memory is accurate but truncated at the dropped-field wording.
- **UPDATED** `fc7745b7-5c2` — Verified against current migrations, models, enrollment router/template, auth callback, and teacher join-code validation; the old memory omitted co_teacher_password and current /enroll profile fields.
- **UPDATED** `ac4d10f1-6b8` — Confirmed against migration 0016, CustomProblem model, teacher authoring path, render_to_snapshot, sandbox runner, and problem registry. The memory is substantively correct but truncated; corrected text completes it and clarifies script-row variables are [] rather than null.
- **UPDATED** `7c173bfb-797` — Codex was right. Actual code confirms the routes, lazy-loaded Modules tab, built-in viewer seeds/template, and View/Edit buttons; the stale part was that module card markup now lives in _module_browser.html included by _modules_panel.html.
- **UPDATED** `bb2eeb12-b83` — Confirmed against live code. Codex was right: the memory was partially stale because grading is Fraction-based but tolerant, not strict exact equality, and rref_B usage should be scoped to q2-q7 with q1/q8-q10 excluded.
- **UPDATED** `3d61d8a7-e9b` — Verified the migration, models, folder service, mounted routers, admin routes, and templates. Codex was right that the old memory was truncated/incomplete and needed the current router/UI paths clarified.
- **UPDATED** `acccce19-73d` — Confirmed in the actual code and migrations. Codex was right that the memory is partially stale: it misses the 0048 source-signature invalidation behavior and overstates the removal of source PROMPT_TEMPLATE constants.
