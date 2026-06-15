# Memory Verification Report — 2026-06-15 02:46

Checked: 20 | Stale: 10 | Fixed: 9 | Deleted: 0 | Errors: 0 | Skipped recent: 220

- **UPDATED** `c73143f4-e15` — Codex was right: the code confirms the original memory is true but incomplete; current run_income_appointments_report also uses the Square match report, Paid-with-All payments, live DASYS refreshes, and pending insurance persistence.
- **UPDATED** `ce89971f-01c` — Confirmed against startup_code/bump_android_version.py, jane_web/main.py, and startup_code/graceful_restart.sh. Original memory is substantively right but truncated and slightly conflates _resolve_android_apk_path with the latest-version metadata endpoint.
- **KEPT** `740dc143-e91` — Codex was wrong to mark this partial: code confirms the FastAPI/Jinja2/HTMX/SQLAlchemy app, local dev/proxy assumptions, and GCP identifiers; live gcloud also verifies classes.chiehwu.com maps to route teaching-app-v2 and Cloud SQL has database teaching_app on teaching-app-db.
- **UPDATED** `2ac56219-976` — Confirmed against the actual v2/v3 pipeline code. Codex was right: the architecture claim holds, but the function name was truncated and should be _persist_turn_to_fifo.
- **UPDATED** `046fc30a-7ec` — Confirmed from configs/VESSENCE_SPEC.md, jane_web/main.py, and the essence loader/runtime code. Codex was substantively right; the stored memory is truncated and should be replaced.
- **UPDATED** `297ceaab-92d` — Confirmed from jane/config.py and test_code files: paths and generator exist, TESTS.md claims source-of-truth status, but it is stale with 88 top-level files versus 45 registry rows and 12 stale listed files. Original memory's regeneration command was truncated.
- **UPDATED** `473c4e96-5ac` — Repo, git, Cloud Run, migration files, and live Cloud SQL checks confirm the old deployment snapshot is stale; Codex was mostly right, but live alembic is now verified as 0077_section_event_border_color.
- **UPDATED** `00698b9a-68f` — Confirmed from jane_proxy.py, llm_brain/v1/standing_codex.py, llm_brain/v1/persistent_codex.py, live process env, and logs. The stale part is that current default Codex routing uses standing_codex/app-server roots, not persistent_codex --add-dir.
- **UPDATED** `e06d26a9-c53` — Verified with git status/show/merge-base/ls-remote, local gcloud logs, and live Cloud Run describe; memory is stale, and Codex was right except its Vessence origin/master SHA was wrong.
- **UPDATED** `7556a72f-52d` — Codex was right: code confirms the label preference/fallback, lsblk confirms the ext4 label/UUID, and logs confirm the syncs/snapshots and later no-USB errors, but available code/log searches did not verify the old Backup Plus restore claim.
