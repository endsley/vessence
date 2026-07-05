# Memory Verification Report — 2026-07-05 02:42

Checked: 20 | Stale: 12 | Fixed: 12 | Deleted: 0 | Errors: 0 | Skipped recent: 249

- **UPDATED** `0b71af24-159` — Confirmed the service unit and direct backend.* import failure from the backend cwd; Codex was right that the old crash implication is stale because the current wrappers fall back to top-level imports.
- **UPDATED** `2b8e17ab-9cc` — The path, symlink, and manifest metadata are current. Codex was right that the 8 AM/6 PM manifest schedule is stale/ambiguous and that news_fetcher.py defaults to qwen2.5:7b, but it overstated essence_scheduler as the active scheduler: current crontab runs Daily Briefing directly at 2:10 AM.
- **UPDATED** `15937b95-ab3` — Codex was right: the current code confirms the substantive claims, but the existing memory is truncated at the end and should be repaired.
- **UPDATED** `47b260f4-153` — Confirmed against setup.sh, startup_code/first_run_setup.py, startup_code/install_codex_skills.py, codex_skills, and ~/.codex/skills. Codex was right; the architecture is current and the stored memory is stale only because its final sentence is truncated.
- **UPDATED** `655b0dea-7d0` — Codex was right: the code-backed claims still match jane_web/attachment_context.py, jane_v2/jane_v3 pipelines, ChatViewModel.kt, ChatRepository.kt, and ChatRequest; only the original memory's final Android sentence was truncated.
- **UPDATED** `33f29c3b-dc8` — Confirmed from code and filesystem: Codex was right that the core split is still true, but the memory needed caveats for missing manifest type defaults, MCP-style skill folders, and legacy TOOLS_DIR users.
- **UPDATED** `78c35991-0ca` — Confirmed in actual code: Gradle and changelog behavior still match, bump_android_version.py still handles versioning/build/deploy/marketing links, but the main.py fallback-literal update claim is stale because main.py now reads through ReleaseDownloads and the helper regex no longer matches.
- **UPDATED** `80d5763d-bd7` — Verified against jane/config.py, jane_web/jane_v2/models.py, jane_web/model_settings.py, jane_web/main.py, jane_web/env_settings.py, and llm_brain/v1/standing_brain.py. Codex was right that the old memory is truncated/incomplete and needs the current env vars plus the local-model source-of-truth note.
- **UPDATED** `3e6256d1-d80` — Source review confirms Codex was mostly right, but live crontab is readable here and the cron drift details needed updating.
- **UPDATED** `2f463691-64e` — Codex was right: the behavior still matches, but provider resolution and the persistence predicate now live in `jane_web/proxy_brain.py` and are imported by `jane_web/jane_proxy.py`.
- **UPDATED** `1f69f5e7-dac` — Current code confirms the original StandingBrainManager facts but the memory is incomplete because Codex now has a separate standing_codex app-server path enabled by default for web/Android, with persistent/direct fallbacks.
- **UPDATED** `deffa535-8a1` — Actual code confirms Codex's verdict overall; the old memory is truncated at `--set` and omits the shared helper and non-Claude command shapes.
