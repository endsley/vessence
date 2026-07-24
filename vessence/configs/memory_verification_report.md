# Memory Verification Report — 2026-07-24 01:27

Checked: 40 | Stale: 14 | Fixed: 14 | Deleted: 0 | Errors: 0 | Skipped recent: 199

- **UPDATED** `a9942a35-8ff` — Codex was right: code and live user service env confirm the timeout/redirect behavior; only the service name was truncated.
- **UPDATED** `0cc009cd-d02` — Actual code confirms Codex was right: the old symbols remain, but helper delegation and scanning both tools and essences directories make the previous memory incomplete/stale.
- **UPDATED** `9fa2262d-71d` — Codex was right: current code confirms the helper, streaming upload body, unauthenticated crash endpoint, v0.2.90 changelog entry, and current version v0.2.102/code 333; the memory was truncated and needed the current ChatRepository path.
- **UPDATED** `655b0dea-7d0` — Confirmed against jane_web/attachment_context.py, jane_v2/jane_v3 pipelines, ChatViewModel.kt, ChatRepository.kt, ChatMessage.kt, and main.py; Codex was right that the Android sentence was incomplete.
- **UPDATED** `a310e22e-fdd` — Confirmed in code: Gradle and ReleaseDownloads read version.json, main.py assigns from read_android_version(), and bump_android_version.py still runs regexes for literal main.py constants that no longer exist.
- **UPDATED** `d0690a2e-8eb` — Actual code confirms Codex was right: the endpoint and loader still exist, but the UI path is `vault_web/static/essences.html`, tools-dir fallback includes `ESSENCES_DIR`, and discoverability, loaded state, and active state are separate checks.
- **UPDATED** `78c35991-0ca` — Codex was mostly right, but actual code shows APK verification is conditional and main.py is not effectively updated because the script regex matches no current constants.
- **UPDATED** `ba8740f1-36a` — Actual code checks v3 before v2, should_use_v3_pipeline only checks JANE_USE_V3_PIPELINE, and live PID 368142/env confirm the runtime values.
- **UPDATED** `3e6256d1-d80` — Verified the 11 completed job files and timestamps, confirmed configs/CRON_JOBS.md exists, and confirmed configs/crontab is absent while crontab -l contains the active schedule.
- **UPDATED** `2f463691-64e` — Codex was right: the named code paths exist and are current, but the stored memory is incomplete because it ends mid-sentence.
- **UPDATED** `072972dd-578` — Verified in agent_skills/consult_panel.py, consult_panel_helpers.py, CLAUDE.md, daily_code_review.py, and crontab. Codex was right that gemini is stale; FRONTIER_CLIS now uses agy, codex, and claude.
- **UPDATED** `27c44480-2e6` — Live crontab has exactly one active nightly_self_improve entry and it matches the 23:30 flock/timeout/nice/ionice command; configs/crontab_backup.txt matches and the log shows 23:30 starts. The old 01:00 bare command is stale.
- **UPDATED** `4d22a27f-a20` — Confirmed in code: the symlink exists, config.py defines SKILLS_DIR/TOOLS_DIR as described, and tool_loader.py uses JANE_TOOLS_DIR/default ~/ambient/skills without importing jane.config. The stale part was the inaccurate jane.config.SKILLS reference.
- **UPDATED** `0e79d2ac-b55` — Confirmed in `jane_web/main.py`, `jane_web/pipeline_selection.py`, `jane_web/jane_v2/models.py`, `intent_classifier/v3/classifier.py`, and `/home/chieh/ambient/vessence-data/.env`; the original memory was truncated and omitted the actual v2/v1 fallback and current qwen model.
