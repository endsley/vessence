# Memory Verification Report — 2026-07-18 01:23

Checked: 40 | Stale: 19 | Fixed: 19 | Deleted: 0 | Errors: 0 | Skipped recent: 130

- **UPDATED** `5001554f-1cc` — Confirmed from actual repository files and live crontab: Codex was right that the old memory's 02:00/live-crontab claim is stale, while the wrapper and harvest-then-summarize pipeline remain correct.
- **UPDATED** `1ec8aa82-4b3` — Actual files confirm the stack, absent legacy directory, no README legacy reference, and production service teaching-app-v2; Codex was essentially right, with the nuance that CLAUDE.md uses the tilde path.
- **UPDATED** `eef09673-adb` — Verified actual code and environment; Codex was right that the stored memory is truncated at the final path.
- **UPDATED** `a04927a6-a64` — Confirmed from git status/log, .gitignore, tracked/ignored file checks, and the backend/frontend source; the old memory had stale HEAD/main details and was truncated.
- **UPDATED** `52389d73-e52` — Verified in code: the schema and UI details are still true, but teacher.py no longer strips/stores directly; it delegates to create_professor_section.
- **UPDATED** `acacc0e7-035` — Read the actual files: all path/class claims still hold, but q2.py’s docstring says “HW2 A2 — Chemistry Mixing,” not “Chemistry Mixin.”
- **UPDATED** `cd2e63a1-51a` — Confirmed in code: accounting.py has save/load helpers, accounting_fsb_bank.py saves uploads after a successful FSB run, nightly_update_current_month_reports.py reloads them and calls use_cache=False, and crontab runs the wrapper daily at 01:30. Git history/blame attributes the original implementation to 2026-06-25, not 2026-06-24; the restart note is stale.
- **UPDATED** `95db60cc-111` — Confirmed from the completed job doc, local systemd service files, live Cloudflare zone/DNS/tunnel configuration, and local/live HTTP probes; the old memory had the stale job path and omitted the current backend routing.
- **UPDATED** `d17c2f11-9aa` — Confirmed from the actual systemd unit files and backend/main.py; Codex was right that only the waterlily-auth.service WorkingDirectory/ExecStart detail was stale.
- **UPDATED** `aaf029b2-47f` — Confirmed in README.md and agent_skills/edu_homework_audit.py that Vessence teaching-app DB access is via local Cloud SQL Auth Proxy on 127.0.0.1:3307; repo search found no ipify or public-IP Cloud SQL allowlist logic. Original memory was truncated and needed the Vessence exception clarified.
- **UPDATED** `8490fd20-135` — Confirmed in actual code: events.py/schema/route exist, but /events/index.html only loads auth.js and public.js and contains static event markup, with no /api/events fetch or eventlist.js load.
- **UPDATED** `7e71fb40-863` — Verified backend/main.py has active /admin, /admin/accounting, /admin/events, /studio, and /api/space-requests routes; /admin/jane only appears in ARCHITECTURE.md as a removed route surface.
- **UPDATED** `80372137-8b7` — Verified the actual repository files; Codex was right that the architecture claims hold and the stale part was the truncated GCP project id.
- **UPDATED** `7373c511-53a` — Confirmed from the actual model, migrations, form parser, runtime renderer, and sandbox code; the old memory had the parser location partially wrong and omitted script mode/new variable kinds.
- **UPDATED** `426c9797-dcf` — Codex was right: the extractor still exists, but EXTRACT_KEYS moved to short_term_structured.py and now includes purpose/scope/outcome/current_status; should_skip now permits those work-detail fields.
- **UPDATED** `2bca4180-d4d` — Read the Waterlily templates/scripts: the paid appointment disclosure rows and listed fields remain, but the section heading is now set to Appointments of the selected month, not Paid Appointments.
- **UPDATED** `c35535a3-eb0` — Codex was right: the function and hint table moved, the Terro/pest hints are absent, deterministic fallback is Other expenses with blank subcategory, and Gemma can later override fallback categories.
- **UPDATED** `b7c370b1-fce` — Confirmed from startup_code/auto_pull.sh, startup_code/startup_env.sh, live crontab, and configs/crontab_backup.txt; the old memory's explicit AMBIENT_BASE/Python path claims are stale.
- **UPDATED** `89e50333-91d` — Stale. Code confirms the migration/model still exist, but parse_variables_form/build_problem_attrs moved to custom_problem_forms.py, runtime/previews/sandbox code is split out, rows are module_id-scoped, and script-mode exists.
