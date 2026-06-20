# Memory Verification Report — 2026-06-20 03:21

Checked: 20 | Stale: 17 | Fixed: 17 | Deleted: 0 | Errors: 0 | Skipped recent: 208

- **UPDATED** `0f26b102-9f9` — Confirmed in accounting.py and main.py. Codex was right: the old memory was too broad about package sessions and reversal handling.
- **UPDATED** `2b8e17ab-9cc` — Confirmed against manifest.json, daily_briefing.mcp.json, cron/jobs.json, custom_tools.py, news_fetcher.py, live crontab -l, configs/crontab_backup.txt, and CRON_JOBS.md. Codex was right about the stale operational schedule/model details, except crontab -l was readable here.
- **UPDATED** `15937b95-ab3` — Codex was right on the code-backed parts after reading the current source; the exact historical DB row details are not confirmable from code alone.
- **UPDATED** `47b260f4-153` — Confirmed from README, AGENTS, setup.sh, first_run_setup.py, and install_codex_skills.py. The policy/setup wiring is accurate, but runtime ~/.codex/skills has many skills absent from codex_skills, and dry-run shows schedule-ds3000-homework would be updated, so the original overstates current coverage/sync.
- **UPDATED** `9fa2262d-71d` — Codex was right: the v0.2.90 history and camera/crash-report fixes are supported by the code and changelog, but the latest-version claim is stale because current version.json is 0.2.93/code 324 and the endpoint builds the v0.2.93 download URL.
- **UPDATED** `236bb058-a93` — Confirmed against `jane_web/reverse_proxy.py` and `configs/systemd/jane-proxy.service`; Codex was right that the original memory was substantively accurate but truncated at `configs/systemd/`.
- **UPDATED** `655b0dea-7d0` — Codex was right: source confirms the current attachment expansion and Stage 3 bypass paths; the 2026-06-04 Boston parking-ticket live proxy test is not present in current code/search results, so remove that historical claim.
- **UPDATED** `a310e22e-fdd` — Confirmed against the actual files. Codex was substantively right, but the memory has a stray trailing `T` and the APK verification/deployed-APK scan depend on Android SDK tools being available.
- **UPDATED** `d0690a2e-8eb` — Code confirms the memory was incomplete and overstated Android reachability; Codex was right, with an additional confirmed Android active-endpoint type mismatch.
- **UPDATED** `33f29c3b-dc8` — Confirmed against jane/config.py, agent_skills/essence_loader.py, current manifests, and filesystem paths. Codex was right that the memory is substantively correct but truncated/incomplete.
- **UPDATED** `80d5763d-bd7` — Verified jane/config.py, jane_web/jane_v2/models.py, router files, and the runtime .env; the old memory was accurate in core idea but truncated and missing the frontier-vs-local model distinction.
- **UPDATED** `ba8740f1-36a` — Verified main.py routing, jane_v2/v3 classifier code, models.py, the systemd EnvironmentFile, and the live jane-web process env. Codex was right that the stale part is the claim that both jane_v2 and jane_v3 are active pipelines; v3 is the active route when enabled, while v2 is fallback/shared infrastructure.
- **UPDATED** `3e6256d1-d80` — Codex was mostly right on completed jobs and v3 routing, but wrong/outdated about live crontab readability; live crontab is readable and confirms active job_queue_runner plus active auto_pull drift.
- **UPDATED** `2f463691-64e` — Confirmed against `jane_web/jane_proxy.py`, `jane/config.py`, and `llm_brain/v1/persistent_claude.py`; Codex was right that the existing memory is accurate but truncated.
- **UPDATED** `33ddf8fd-5b8` — Confirmed Codex's partial verdict against jane_web/main.py, vault_web/templates/jane.html, context_builder/v1/context_builder.py, agent_skills/essence_loader.py, and the tax_accountant_2025 manifest. The stale part is the active display-name vs folder-name mismatch.
- **UPDATED** `1f69f5e7-dac` — Actual code confirms the old memory's paths and single BrainProcess detail, but it omitted the current standing_codex OpenAI/Codex path and the default Gemini API routing.
- **UPDATED** `deffa535-8a1` — Confirmed against the actual code. The original memory was partially stale/incomplete about Claude hook gating and OpenAI standing-process behavior.
