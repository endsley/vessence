# Memory Verification Report — 2026-07-23 01:39

Checked: 40 | Stale: 18 | Fixed: 18 | Deleted: 0 | Errors: 0 | Skipped recent: 160

- **UPDATED** `7556a72f-52d` — Confirmed from startup_code/usb_sync.py, crontab -l, and findmnt/lsblk; the old memory was truncated and missed the disabled cron/docstring mismatch.
- **UPDATED** `d83ab134-93a` — Actual code confirms the old memory is mostly accurate but incomplete/truncated and missing the manager-only and force_refresh behavior.
- **UPDATED** `398b73f7-b00` — Confirmed from live crontab and /home/chieh/code/waterlily/scripts/backup_waterlily_history.py; Codex was right about the cron wrappers and backup/mount behavior. The script's generated restore note still shows the older bare cron example, but the live crontab uses the wrapped command.
- **UPDATED** `032cc1f6-19b` — Confirmed in code; Codex was right that the write helper is plural _write_active_essences, not _write_active_essence.
- **UPDATED** `5fbb727b-767` — Codex is right: I confirmed `jane_web/main.py` exists, and the stored memory is incomplete because it ends mid-sentence at “Full/absolute”.
- **UPDATED** `3584ff36-f64` — Code confirms the paths and downloader flow; fallback is only allowed for DasysMonthlyPdfUnavailableError after verified target-period absence, while drift/duplicates/ambiguous or partial target-month labels raise contract errors.
- **UPDATED** `90bd494a-c15` — Codex was wrong that the v0.2.91 introduction was unverifiable: current source confirms the architecture, and local APK artifacts show v0.2.91 was built on 2026-06-17 with camera-sync strings absent from v0.2.90. Updating mainly to complete and clarify the truncated memory.
- **UPDATED** `87216a75-255` — Confirmed from the service unit, run_profile_watcher.sh, watch_agent_profile.py, sync_agent_profile.py, repo origin, and live watcher process; the old memory described obsolete watch_codex_skills.py startup behavior.
- **UPDATED** `deaccc58-11e` — Code confirms the API path, skill call, and delegation, but the old memory omitted newer source artifacts and enrichment paths; Codex's PARTIAL verdict is right.
- **UPDATED** `73d8ea6f-fcc` — Actual code confirms the delegation and omitted force_refresh, but the live fresh branch now passes fallback_to_cache_on_error=False, not True.
- **UPDATED** `24753619-73b` — Confirmed in /home/chieh/code/waterlily: the six clean-route index pages and redirect stubs exist, nav uses clean routes, and events/ contains only index.html.
- **UPDATED** `82ccc192-372` — Codex was right: code matches insurance by service date+amount+identity, defers paid claims without report-month receipt evidence, and enforces current DASYS CSV freshness/attestation; Lace June 2026 is only historical repair context.
- **UPDATED** `b7681cc2-e5c` — Confirmed in configs/project_specs/vessence.md; original memory is accurate but truncated. agent_skills/memory/__init__.py also confirms v1 ChromaDB is production.
- **UPDATED** `37c3c677-9fe` — Confirmed in actual code: graceful_restart.sh sources startup_env.sh and uses exported variables; it does not hardcode the roots. The other path claims are correct.
- **UPDATED** `707720f5-659` — Confirmed by reading jane/config.py, jane_web/jane_v2/models.py, and grep results; the old memory was truncated after LOCAL_LLM_MODEL.
- **UPDATED** `c1874433-4b9` — Codex was right: config targets/TODOs are still present and unchecked, no Stripe SDK/dependency or Vessence payment implementation exists, but active receipt modules contain Stripe invoice-link handling.
- **UPDATED** `9659c4f4-cb8` — Code confirms `SHORT_TERM_TTL_DAYS = 30`, explicit writes use that default, and nightly `run_janitor()` passes `FORGETTABLE_MAX_AGE_DAYS = 30`; the old ~14-day claim is stale even though the helper function has a legacy default argument of 14 when called directly.
- **UPDATED** `aa8acff2-18e` — Verified configs/VESCAB.md, jane_web/main.py, jane.config/llm_brain/context_builder imports, and current crontab; Codex was right and the original memory incorrectly marked essence loading stale.
