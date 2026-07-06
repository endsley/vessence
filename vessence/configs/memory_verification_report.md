# Memory Verification Report — 2026-07-06 02:55

Checked: 20 | Stale: 13 | Fixed: 12 | Deleted: 0 | Errors: 0 | Skipped recent: 250

- **UPDATED** `00b6964f-f83` — Confirmed against /home/chieh/code/waterlily code. Codex was right: the reconciliation_context pieces exist, but the cached error-check route disables both AcuBliss source-link backfill and reconciliation_context refresh, so the old cached-display claim was stale/truncated.
- **UPDATED** `8233574a-5be` — Codex was right that the old memory's line numbers were stale and the wait_until_safe() call-site list was incomplete; code also shows an additional should_defer() resource gate in essence_scheduler.py.
- **UPDATED** `072972dd-578` — Code confirms the policy and behavior; the stale part is the guidance filename, which is CLAUDE.md, not CLAUDE.
- **KEPT** `27c44480-2e6` — Codex was wrong to mark this partial here: I read `agent_skills/nightly_self_improve.py`, `configs/crontab_backup.txt`, live `crontab -l`, and the orchestrator log. The live crontab and backup each have exactly one uncommented exact entry, the code still uses the stated Python path/log, and the log shows the 2026-07-06 01:00:01 run.
- **UPDATED** `90ed78a5-a4d` — Codex was right: the old memory is truncated and missing caveats; code confirms the active Stage 3 path and skip/filter behavior.
- **UPDATED** `cbba9406-4a9` — Confirmed against AGENTS.md, jane_web/jane_v2/models.py, and jane/config.py. Codex was right: the substantive claims are current; only the dangling trailing fragment `Wit` should be removed.
- **UPDATED** `e75d7ba1-c90` — Verified against `configs/MCP_SPEC.md`, `jane/tool_loader.py`, and `/home/chieh/ambient/skills`; Codex was right that the stored memory is truncated/incomplete.
- **UPDATED** `160c0bce-9ec` — Verified against the actual loader, context builder, proxy, model code, Daily Briefing fetcher, live crontab, and cron docs. Codex was mostly right, but the crontab is now readable and the loader's current skipped folders should be captured.
- **UPDATED** `ac06e647-af7` — Codex was right: the stored memory is truncated, and the current code confirms mcp.json is required while prompt.md and server hooks are optional/lenient.
- **UPDATED** `0845b572-f6a` — Verified the repo root, hook config, pre-commit kernel list, tracked symlink/ignored skills state, tool_loader default path, hygiene script failures, and LOCAL_LLM default from the actual checkout; Codex's correction is substantively right.
- **UPDATED** `0e79d2ac-b55` — Code confirms the original memory's substantive claims, but it is truncated. I verified the route selection in `jane_web/main.py`, live process env, model source in `jane_web/jane_v2/models.py`, v3 ChromaDB+qwen classifier code, and multi-user/session scoping files.
- **UPDATED** `df317381-9eb` — Confirmed in source, manifest, Gradle, generated tool sources, and the external phone tool source; Codex was right substantively, but the stored memory is truncated.
- **UPDATED** `02864895-c62` — Confirmed against current code. The old memory's main claims are still correct, but it is truncated and omits ArticleReaderV2Activity as another HybridTtsManager instantiation.
