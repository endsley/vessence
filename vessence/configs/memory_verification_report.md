# Memory Verification Report — 2026-06-28 02:43

Checked: 20 | Stale: 13 | Fixed: 13 | Deleted: 0 | Errors: 0 | Skipped recent: 222

- **UPDATED** `470ac132-e22` — Codex was right: the first file matches, but the second sets bluetooth.autoswitch-to-headset-profile, not bluetooth.autoswitch-to-headset. bluetoothctl confirms 56:EB:2B:51:EF:B0 is MusiBaby-M68.
- **UPDATED** `6852a648-d83` — The original WL_PUBLIC_HOST=https://test detail is stale; actual service/config use https://test.waterlilywellness.com. Codex was right about the host, tunnel, and Gemma path, but wrong that there are no Waterlily cron entries.
- **UPDATED** `2c894759-104` — Codex was mostly right about receipt support and Gemma behavior, but its suggested taxonomy wording was still partly wrong: current saved auth.db taxonomy has Office supplies -> Others, while Other expenses -> Items that do not fit elsewhere comes from the default/legacy fallback and effective email taxonomy.
- **UPDATED** `693535da-e7a` — Code confirms the pipeline, raw .eml storage, raw_email_file_url, Gemma default model, and auto-import path. Codex was wrong that d48 was not found: Wrangler logs contain it for 2026-06-11. The stale part is waterlily-auth-codex/current-version wording: only waterlily-auth.service is present, and local logs show a later worker deploy.
- **UPDATED** `dc5bde39-0f3` — Codex is right: the backend route and attach behavior are current, but the UI claim was stale because controls are rendered in admin_accounting_cost_scripts.html and the labels changed.
- **UPDATED** `f2096c46-be3` — Codex was wrong: it searched the wrong repo. The actual Waterlily repo is /home/chieh/code/waterlily, where the code and active/backup DB rows confirm the bug and fix. Updated only for the current parser module location.
- **UPDATED** `ce382ed9-746` — Actual code confirms the global AppSetting storage, no Module latex_macros field, migration history, and module_macros cache/write behavior; only the UI template path was stale because _modules_pane is missing and _modules_panel.html is current.
- **UPDATED** `fd478e39-b62` — Confirmed against agent_skills/google_cloud_receipts.py; Codex was right about the workflow, and the existing memory is truncated at the end.
- **UPDATED** `136c24ff-98c` — Actual code confirms the workflow and script path, but _default_out_dir() and the --out-dir help show the default is a timestamped ~/Downloads/google_cloud_receipts_<timestamp>/ directory, not plain ~/Downloads/.
- **UPDATED** `da8286ca-8ab` — Actual code and env confirm the substantive claims, but the stored memory is truncated after `then sends STA`, so it needs a completed correction.
- **UPDATED** `fa8de932-f4d` — Confirmed against q6.py through q10.py and the dynamic problem registry. Codex was right: the old q10 text uses stale variable spelling 'budg' and omits that q10 asks for the gradient at the maximizing point.
- **UPDATED** `dca272e8-326` — Confirmed against actual code: the old REGISTRY.by claim is stale; attempts.py now uses REGISTRY.by_topic(...) and REGISTRY.get(...). Other listed files and registry usage still exist.
- **UPDATED** `d6737ef0-b55` — Confirmed against actual code: migration files end at 0077, all listed migrations exist, and LaTeX macros are global via app_settings/module_macros. Original memory was truncated at trailing 'Late'.
