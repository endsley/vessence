# Memory Verification Report — 2026-06-06 01:49

Checked: 20 | Stale: 11 | Fixed: 11 | Deleted: 0 | Errors: 1 | Skipped recent: 187

- **UPDATED** `85330474-469` — Actual README/ARCHITECTURE/backend code, service units, listening ports, curl checks, py_compile, and SQLite reads confirm Codex was right that the architecture is current and the old count snapshot is stale; live service activity is also directly confirmed here.
- **UPDATED** `072972dd-578` — The consult_panel implementation matches the memory, but the text was truncated/partial. Codex was also incomplete: interactive use is manual, but there is an automated daily_code_review.py cron path that calls consult_panel.
- **UPDATED** `27c44480-2e6` — Codex was mostly right on the code and backup, but wrong that the live crontab could not be read here; `crontab -l` confirms exactly one matching live entry. Updated with current verification date and exact JOBS list.
- **UPDATED** `90ed78a5-a4d` — Confirmed the main Stage 3 path in code. The memory needed nuance: writes are conditional, Stage 2 skips the Chroma per-turn note, and legacy theme/topic machinery remains but is not the active Web/Android write path.
- **UPDATED** `cbba9406-4a9` — Confirmed from actual code and env. Codex was right that the memory is partial/stale, but it missed additional hardcoded local-model fallbacks beyond stop_hook_memory.py.
- **UPDATED** `e75d7ba1-c90` — Verified against current code and skills directory. Codex was mostly right on loader behavior and visible skills; the memory was stale/truncated, and the routing nuance is that main.py now selects v2 by default via JANE_PIPELINE while JANE_USE_V2_PIPELINE remains in the older proxy path.
- **UPDATED** `160c0bce-9ec` — Verified the relevant source, Daily Briefing code, live crontab, and cron docs. Codex was right that the memory was partial/stale; I also confirmed the Daily Briefing model description in `CRON_JOBS.md` is stale.
- **UPDATED** `ac06e647-af7` — Confirmed against current code and configs. Codex was mostly right, but it overstated `get_tool_mcp` runtime usage and missed that current env enables the v3 qwen-based pipeline.
- **UPDATED** `0e79d2ac-b55` — Verified against source and current runtime config. Codex was right that the `JaneSessio...`/`JaneSession` part is stale, but wrong that the active crontab is empty; it is active and inconsistent with repo cron docs/configs.
- **UPDATED** `df317381-9eb` — Confirmed from Android manifest, Kotlin sources, phone tool files, email_tools.py, marketplace modules, cron docs, and model config; Codex's PARTIAL verdict is right.
- **UPDATED** `02864895-c62` — Confirmed Codex was mostly right from source and live crontab: local Android TTS is active, server TTS remains wired but disabled/inactive by default, ArticleReaderV2 uses HybridTtsManager rather than AndroidTtsManager directly, and the auto_pull cron documentation is stale.
