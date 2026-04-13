# Cron Job Registry

This document logs all scheduled tasks (cron jobs) for the system. It must be updated whenever a cron job is added, removed, or modified.

---

## 1. Memory Janitor
- **Schedule:** `15 2 * * *` (Runs daily at 2:15 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/memory/v1/janitor_memory.py`
- **Description:** Performs maintenance on the vector memory, cleaning up old or redundant entries.

## 2. Bot Watchdog — DISABLED (Discord disconnected 2026-03-22)
- **Schedule:** `*/3 * * * *` (COMMENTED OUT)
- **Script Path:** `$VESSENCE_HOME/startup_code/bot_watchdog.sh`
- **Description:** Monitors Amber Brain, Amber/Jane Discord bridges, and Jane Web. Uses multi-attempt probes, consecutive-failure thresholds, and a restart cooldown so a single transient stall does not trigger a restart. For Jane Web: checks port 8081, kills duplicate uvicorn processes (keeps the oldest), and starts the service if it is down.

## 3. Identity Essay Generation
- **Schedule:** `0 3 * * *` (Runs daily at 3:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/generate_identity_essay.py`
- **Description:** Regenerates or updates the identity essays based on recent interactions and memories. This is a core part of the agent's self-reflection process.

## 4. Update Checker
- **Schedule:** `30 2 * * *` (Runs daily at 2:30 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/check_for_updates.py`
- **Description:** Checks for updates to the agent's own codebase or dependencies.

## 5. Update Notifier
- **Schedule:** `0 10 * * *` (Runs daily at 10:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/notify_updates.py`
- **Description:** Notifies the user about any available updates found by the `check_for_updates.py` script.

## 6. System Janitor
- **Schedule:** `0 3 * * *` (Runs daily at 3:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/janitor_system.py`
- **Description:** Performs system-level cleanup: removes temp files, rotates oversized logs, and deletes log files older than 2 days from the runtime logs tree.

## 7. USB Incremental Sync Backup
- **Schedule:** `0 2 * * *` (Runs daily at 2:00 AM)
- **Script Path:** `$VESSENCE_HOME/startup_code/usb_sync.py`
- **Description:** Incremental rsync to a single `current/` mirror on USB — only transfers changed files. Weekly hard-link snapshots for point-in-time history (kept 30 days). Replaces `usb_rotation.py` which copied everything each run.

## 8. Automatic Screen Dimmer
- **Schedule:** `*/30 * * * *` (Runs every 30 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/screen_dimmer.py`
- **Description:** Checks the sunset time online for zip code 02155. If the current time is after sunset, it dims the primary monitor (DP-1) to 30% brightness using `xrandr`.

## 9. Project Ambient Heartbeat
- **Schedule:** `0 5 * * *` (Runs daily at 5:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/ambient_heartbeat.py`
- **Description:** Autonomous research & spec refinement loop for Project Ambient. Skips if user was active in Claude Code within the last 20 minutes (checks JSONL session file mtimes). Per run: searches DuckDuckGo for 9 predefined spec topics, synthesizes findings with qwen2.5-coder:14b, injects research notes into `ambient_app.md`, checks if Phase 1 tasks are implementation-ready (all open questions answered), implements up to 3 tasks per run via the shared automation runner, and sends a Discord summary. Research results cached per-topic for 7 days to avoid redundant calls.

## 10. Jane Context Regeneration
- **Schedule:** `15 3 * * *` (Runs daily at 3:15 AM)
- **Script Path:** `$VESSENCE_HOME/startup_code/regenerate_jane_context.py`
- **Description:** Rebuilds the condensed architecture boot context file (`/home/chieh/.claude/hooks/jane_context.txt`) from authoritative source configs (TODO_PROJECTS.md, Amber_architecture.md, CRON_JOBS.md). This file is injected into every Claude session via `jane_context_hook.sh` to guarantee Jane always knows her architecture, active projects, and operational rules without relying on manual init steps.

## 11. Job Queue Runner
- **Schedule:** `*/5 * * * *` (Runs every 5 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/job_queue_runner.py`
- **Description:** Processes jobs from the job queue (`configs/job_queue/*.md`). Runs every 5 minutes, picks the next pending job, executes it via the shared automation runner, and logs results.

## 12. Autonomous Prompt Queue Runner — NOT CRON-SCHEDULED
- **Script Path:** `$VESSENCE_HOME/agent_skills/prompt_queue_runner.py`
- **Description:** Picks the next uncompleted item from `vault/documents/prompt_list.md`, runs it via the shared automation runner. Not currently in the crontab — invoked on-demand or through other mechanisms.

## 13. Ambient Task Research — REMOVED (2026-03-24)
- **Previously:** `*/30 * * * *` and `0 6 * * *` — removed from crontab per the user's request.

## 14. Code & Documentation Audit
- **Schedule:** `0 */6 * * *` (Runs every 6 hours)
- **Script Path:** `$VESSENCE_HOME/agent_skills/nightly_audit.py`
- **Description:** Gathers system state (actual crontab, agent_skills/ files, amber/tools/ files) and runs an audit via the shared automation runner comparing code reality against documentation (CRON_JOBS.md, SKILLS_REGISTRY.md, architecture manifests). Identifies documentation gaps, code issues, and improvement suggestions. Saves full report to `logs/audits/audit_<date>.md` and sends a summary to Discord.

## 15. Daily Briefing Fetch
- **Schedule:** `10 2 * * *` (Daily at 2:10 AM)
- **Script Path:** `/home/chieh/ambient/tools/daily_briefing/functions/run_briefing.py`
- **Description:** Fetches news for all tracked topics via Google News RSS + article scraping, generates brief/full summaries via gemma3:12b, downloads images, generates TTS audio via Docker XTTS (GPU), saves briefing to latest_briefing.json. Also triggered manually via refresh button on web. Wrapped with `timeout 30m` to prevent runaway briefing jobs.
- **Idle check:** Uses `idle_state.json` (not log file mtime) to determine user activity.
- **Changed 2026-03-24:** Hourly → daily. Model: deepseek-r1:32b → gemma3:12b. TTS Docker fixed with --gpus all.

## 16. Essence Scheduler
- **Schedule:** `* * * * *` (Runs every minute)
- **Script Path:** `$VESSENCE_HOME/agent_skills/essence_scheduler.py`
- **Description:** Checks for scheduled essence tasks that are due and dispatches them. Runs every minute to ensure timely execution of essence-defined schedules.

## 17. Audit Auto-Fixer
- **Schedule:** `0 2 * * *` (Daily at 2:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/audit_auto_fixer.py`
- **Description:** Automatically fixes issues found by the nightly audit. Changed 2026-03-24 from every 6 hours to daily.

## 18. Code Map Generator (NEW 2026-03-24)
- **Schedule:** `15 4 * * *` (Daily at 4:15 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/generate_code_map.py`
- **Description:** Regenerates CODE_MAP_CORE.md, CODE_MAP_WEB.md, CODE_MAP_ANDROID.md with function/class/route line numbers. Pure ast.parse + regex, no LLM. Also run on-demand after code editing sessions.

## 19. Evolving Code Map Keywords (NEW 2026-03-25)
- **Schedule:** `10 2 * * *` (Daily at 2:10 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/evolve_code_map_keywords.py`
- **Description:** Reads today's user messages from the SQLite ledger, identifies code-related messages using existing keywords and code map names, extracts new keywords appearing in 2+ code-related messages, and appends them to `CODE_MAP_KEYWORDS` in `jane_web/jane_proxy.py`. Restarts jane-web.service if keywords were added. Caps at 10 new keywords per day. No LLM required.

## 20. Audit Result Jane Web Notifier
- **Schedule:** `0 11 * * *` (Daily at 11:00 AM)
- **Script Path:** `$VESSENCE_HOME/agent_skills/notify_audit_results.py`
- **Description:** Posts the latest code and documentation audit result into Jane web's announcements feed so it appears in chat as a morning status message. Reads the latest saved audit summary from the audit logs and writes a final `queue_progress` announcement to `jane_announcements.jsonl`.

## 20. Process Watchdog (NEW 2026-04-02)
- **Schedule:** `*/5 * * * *` (Runs every 5 minutes)
- **Script Path:** `$VESSENCE_HOME/agent_skills/process_watchdog.py`
- **Description:** Kills zombie Docker containers (stale TTS/build containers), idle Gradle/Kotlin daemons (>10 min idle), and memory hog processes. Prevents resource exhaustion from accumulated build artifacts and abandoned containers.

## 21. Nightly Code Auditor (NEW 2026-04-12)
- **Schedule:** `0 3 * * *` (Runs daily at 3:00 AM, sleep window)
- **Script Path:** `$VESSENCE_HOME/agent_skills/nightly_code_auditor.py`
- **Description:** Autonomous code audit + fix loop. Each night picks one module from `configs/auditable_modules.md` (rotating), uses Claude Opus to generate stress tests, runs pytest, diagnoses any failures, and patches the module. Always works on a `auto-audit/YYYY-MM-DD-HHMM` git branch — if all tests pass, fast-forward merges to master; if fixes can't make tests pass after 3 attempts, reverts and logs to `configs/audit_failures.md`. Successful audits logged to `configs/auto_audit_log.md`. 30-minute time budget per session. Skips when working tree is dirty.

## 22. Pipeline Audit 100 (NEW 2026-04-13)
- **Schedule:** `0 4 * * *` (Runs daily at 4:00 AM, sleep window)
- **Script Path:** `$VESSENCE_HOME/agent_skills/pipeline_audit_100.py`
- **Description:** End-to-end audit of the v2 3-stage pipeline against the last 100 real user prompts from `jane_prompt_dump.jsonl`. Each prompt is run through the live `/api/jane/chat/stream` endpoint and judged by qwen2.5:7b for: (1) Stage 1 classification correctness, (2) Stage 2/3 response quality. Stage 1 misclassifications with a clear correct class are auto-fixed by adding the prompt as an exemplar in ChromaDB. Stage 2/3 issues are logged to `configs/pipeline_audit_report.md` for human review. Runtime ~50 min for 100 prompts.

## NOTE: Automation Provider Rule
- **Critical note for future agents:** Cron jobs and other unattended execution paths must never hardcode a specific coding CLI (`claude`, `codex`, etc.). They must go through the shared automation runner and respect `AUTOMATION_CLI_PROVIDER` (falling back to `JANE_BRAIN` when unset). When switching providers, audit cron jobs, queue runners, background research jobs, and Discord bridges before assuming the cutover is complete.
