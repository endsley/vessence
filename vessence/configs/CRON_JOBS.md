# Cron Job Registry

This document logs all scheduled tasks (cron jobs) for the system. It must be updated whenever a cron job is added, removed, or modified.

> **Note (2026-04-16):** The `$VESSENCE_HOME` env var issue is now resolved — the crontab header defines all necessary env vars explicitly.

---

## 1. Nightly Self-Improve Orchestrator
- **Schedule:** `0 1 * * *` (Runs daily at 1:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/nightly_self_improve.py`
- **Description:** Single entry point that runs ALL nightly self-improvement jobs sequentially with per-job time budgets. Currently dispatches: (1) `doc_drift_auditor.py` — compares registries against filesystem/cron state, auto-fixes safe drifts; (2) `nightly_code_auditor.py` — picks one module, generates tests via Opus, attempts fixes; (3) `pipeline_audit_100.py --n 30 --no-fixes` — replays real prompts through the pipeline and reports misclassifications/response failures without mutating classifier data; (4) `transcript_quality_review.py --skip-fixes` — reviews real transcripts/logs and writes suggested fixes without editing code; (5) `dead_code_auditor.py` — scans for unreferenced files/functions/duplicates. Summary written to `configs/self_improve_log.md`.

## 2. USB Incremental Sync Backup
- **Schedule:** `0 2 * * *` (Runs daily at 2:00 AM)
- **Script Path:** `$VESSENCE_HOME/startup_code/usb_sync.py`
- **Description:** Incremental rsync to a single `current/` mirror on USB — only transfers changed files. Weekly hard-link snapshots for point-in-time history (kept 30 days).

## 2a. Waterlily History Backup
- **Schedule:** `20 1 * * *` (Runs daily at 1:20 AM)
- **Script Path:** `/home/chieh/code/waterlily/scripts/backup_waterlily_history.py`
- **Log:** `$VESSENCE_DATA_HOME/logs/waterlily_history_backup.log`
- **Destination:** USB volume `VESSENCE_BACKUP`, directory `waterlily-history-backup/`
- **Description:** Mirrors Waterlily source plus ignored runtime history needed for crash recovery: `.auth/auth.db` via SQLite backup API, accounting caches/exports, appointment reports, patient payment CSVs, invoices, receipts, email receipt attachments, DASYS claim cache, Waterlily bill cache under `$VESSENCE_DATA_HOME/waterlily/`, `/home/chieh/payment_reports/`, `/home/chieh/payment_report_downloader.py`, and targeted Waterlily/payment report artifacts from Downloads. Writes `restore_manifest.json`, `RESTORE_WATERLILY_HISTORY.md`, checksums, and dated hard-link snapshots.

## 3. Daily Briefing Fetch
- **Schedule:** `10 2 * * *` (Daily at 2:10 AM)
- **Script Path:** `/home/chieh/ambient/skills/daily_briefing/functions/run_briefing.py`
- **Description:** Fetches news for all tracked topics via Google News RSS + article scraping, generates summaries via gemma3:12b, downloads images, generates TTS audio via Docker XTTS (GPU), saves briefing to latest_briefing.json. Wrapped with `timeout 30m`.

## 4. Evolving Code Map Keywords
- **Schedule:** `10 2 * * *` (Daily at 2:10 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/evolve_code_map_keywords.py`
- **Description:** Reads today's user messages from the SQLite ledger, identifies code-related messages, extracts new keywords, and appends them to `CODE_MAP_KEYWORDS` in `jane_web/jane_proxy.py`. Caps at 10 new keywords per day. No LLM required.

## 5. Update Checker
- **Schedule:** `30 2 * * *` (Runs daily at 2:30 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/check_for_updates.py`
- **Description:** Checks for updates to the agent's own codebase or dependencies.

## 6. Identity Essay Generation
- **Schedule:** `0 3 * * *` (Runs daily at 3:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/generate_identity_essay.py`
- **Description:** Regenerates or updates the identity essays based on recent interactions and memories.

## 7. System Janitor
- **Schedule:** `0 3 * * *` (Runs daily at 3:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/janitor_system.py`
- **Description:** Performs system-level cleanup: removes temp files, rotates oversized logs, deletes log files older than 2 days, prunes raw Claude CLI transcripts and Jane session summaries older than 7 days.

## 8. Jane Context Regeneration
- **Schedule:** `15 3 * * *` (Runs daily at 3:15 AM)
- **Script Path:** `$VESSENCE_HOME/startup_code/regenerate_jane_context.py`
- **Description:** Rebuilds the condensed architecture boot context file from authoritative source configs (TODO_PROJECTS.md, architecture files, CRON_JOBS.md).

## 9. Daily Code Review
- **Schedule:** `30 3 * * *` (Runs daily at 3:30 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/daily_code_review.py`
- **Description:** Reviews recent code changes and conversations for quality issues.

## 10. Code Map Generator
- **Schedule:** `15 4 * * *` (Daily at 4:15 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/generate_code_map.py`
- **Description:** Regenerates CODE_MAP_CORE.md, CODE_MAP_WEB.md, CODE_MAP_ANDROID.md with function/class/route line numbers. Pure ast.parse + regex, no LLM.

## 11. Update Notifier
- **Schedule:** `0 10 * * *` (Runs daily at 10:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/notify_updates.py`
- **Description:** Notifies the user about any available updates found by the `check_for_updates.py` script.

## 12. Job Queue Runner
- **Schedule:** `*/5 * * * *` (Runs every 5 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/job_queue_runner.py`
- **Description:** Processes jobs from the job queue (`configs/job_queue/*.md`). Picks the next pending job, executes it via the shared automation runner, and logs results.

## 13. Process Watchdog
- **Schedule:** `*/5 * * * *` (Runs every 5 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/process_watchdog.py`
- **Description:** Kills zombie Docker containers (stale TTS/build containers), idle Gradle/Kotlin daemons (>10 min idle), and memory hog processes.

## 14. Automatic Screen Dimmer
- **Schedule:** `*/30 * * * *` (Runs every 30 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/screen_dimmer.py`
- **Description:** Checks sunset time for zip code 02155. After sunset, dims the primary monitor (DP-1) to 30% brightness using `xrandr`.

## 15. Weather Fetcher
- **Schedule:** `30 */4 * * *` (Runs every 4 hours)
- **Script Path:** `$VESSENCE_HOME/agent_skills/fetch_weather.py`
- **Description:** Fetches current weather and air quality data, caches it for the weather handler to serve without live API calls.

## 16. Todo List Fetcher
- **Schedule:** `*/30 * * * *` (Runs every 30 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/fetch_todo_list.py`
- **Description:** Syncs the todo list from the Google Doc source and caches it locally for quick retrieval by the todo list handler.

## 17. Bot Watchdog — DISABLED (Discord disconnected 2026-03-22)
- **Schedule:** `*/3 * * * *` (COMMENTED OUT)
- **Script Path:** `$VESSENCE_HOME/startup_code/bot_watchdog.sh`
- **Description:** Formerly monitored Amber Brain, Discord bridges, and Jane Web.

---

## 18. Marketplace Harvester + Summarizer
- **Schedule:** `0 2 * * *` (daily 2:00 AM)
- **Script Path:** `$VESSENCE_HOME/startup_code/run_marketplace_cron.sh`
- **Log:** `$VESSENCE_DATA_HOME/logs/marketplace_harvest.log`
- **Description:** Iterates every saved search in `$VESSENCE_DATA_HOME/config/marketplace_searches.json` and for each one runs `python -m agent_skills.marketplace.refresh <name>` — Playwright-based Facebook Marketplace harvest followed by a Stage-2 LLM (qwen2.5:7b via Ollama) summary written to `summary_ai.json` in the search's data dir. The script explicitly unsets `DISPLAY`/`WAYLAND_DISPLAY` so Playwright runs headless regardless of the calling environment. Install line: `0 2 * * * $VESSENCE_HOME/startup_code/run_marketplace_cron.sh`.

---

## 14. Kathia Schedule Scraper
- **Schedule:** `0 */4 * * *` (every 4 hours)
- **Script Path:** `$VESSENCE_HOME/startup_code/run_kathia_schedule.py`
- **Log:** `$VESSENCE_DATA_HOME/logs/kathia_schedule.log`
- **Tracker:** `$VESSENCE_DATA_HOME/clinic_last_pull.json` (last attempt/success timestamp, row count, AI-trigger count, days window)
- **Description:** Two-phase Playwright scrape of Kathia Kirschner's weekly schedule on waterlilywellness.acubliss.app. Phase 1: clicks each appointment and triggers AI summary generation ("Give it a try") for any patient that hasn't had one yet. Waits 30 minutes for AI to finish generating. Phase 2: clicks each appointment again and extracts visit_reason, health_concerns, recommendations, visit_summary from the modal. Saves all data to `$VESSENCE_DATA_HOME/schedule.db` (appointments table). The 30-min wait is skipped if all summaries are already generated. On each run, the wrapper writes `clinic_last_pull.json` atomically — success overwrites, failure preserves the prior `last_success_at`. The wrapper also takes a non-blocking singleton lock at `$VESSENCE_DATA_HOME/logs/kathia_schedule.lock` so overlapping cron invocations exit quietly instead of launching concurrent scrapes.

## 23. Daily Briefing Article Pruner
- **Schedule:** `45 3 * * *` (Runs daily at 3:45 AM)
- **Script Path:** `/home/chieh/ambient/skills/daily_briefing/functions/prune_articles.py`
- **Log:** `$VESSENCE_DATA_HOME/logs/System_log/briefing_prune.log`
- **Description:** Deletes daily-briefing article JSON, image, and audio files older than 14 days. Articles with `state == "saved"` are kept indefinitely. Prevents the briefing listing API from ballooning (was reaching ~900 articles / 3.5 MB list payloads, which made the Android app's first paint of the Daily Briefing essence very slow).

---

## Removed Jobs (historical reference)

| Job | Removed | Reason |
|---|---|---|
| Memory Janitor (`janitor_memory.py`) | ~2026-04 | Superseded by system janitor |
| Ambient Task Research | 2026-03-24 | User request |
| Ambient Heartbeat (`ambient_heartbeat.py`) | ~2026-04 | No longer in crontab |
| Code & Documentation Audit (`nightly_audit.py`) | ~2026-04 | Superseded by nightly_self_improve.py |
| Audit Auto-Fixer (`audit_auto_fixer.py`) | ~2026-04 | Superseded by nightly_self_improve.py |
| Essence Scheduler (`essence_scheduler.py`) | ~2026-04 | Removed from crontab |
| Audit Result Notifier (`notify_audit_results.py`) | ~2026-04 | Removed from crontab |
| Auto Pull (`auto_pull.sh`) | ~2026-04 | Removed from crontab |

---

## Non-Cron Scheduled Scripts

- **Prompt Queue Runner** (`$VESSENCE_HOME/agent_skills/prompt_queue_runner.py`) — invoked on-demand, not cron-scheduled.

## NOTE: Automation Provider Rule
- **Critical note for future agents:** Cron jobs and other unattended execution paths must never hardcode a specific coding CLI (`claude`, `codex`, etc.). They must go through the shared automation runner and respect `AUTOMATION_CLI_PROVIDER` (falling back to `JANE_BRAIN` when unset).
