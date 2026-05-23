# Memory Verification Report — 2026-05-23 02:06

Checked: 20 | Stale: 12 | Fixed: 12 | Deleted: 0 | Errors: 1 | Skipped recent: 85

- **UPDATED** `909d51ad-8ee` — Codex was mostly right on installers, setup, CLI detection, and qwen local model, but wrong to treat `configs/crontab_backup.txt` as cron source of truth and wrong that legacy `vessence-installer-0.0.41.zip` is present.
- **UPDATED** `6baa82c6-fb9` — Confirmed against handler.py, sms_helpers.py, and models.py. Codex was mostly right: recipient resolution and LOCAL_LLM details match, and the stale/ambiguous part is the fast-path wording, because it still emits a visible post-send confirmation text.
- **UPDATED** `45bd5098-fba` — Confirmed against current code. The stale part was treating intent_classifier/v1 as only a fallback import path; it is still used by legacy and compatibility paths, while v2/default serving and memory/v1 production usage remain active.
- **UPDATED** `c9e822b9-0c7` — Confirmed from `startup_code/bump_android_version.py`, `android/app/build.gradle.kts`, `jane_web/main.py`, and `UpdateChecker.kt`. Codex was right that the build/deploy details are mostly current and that `/api/android/*` is stale; the live update route is `/api/app/latest-version` with APK serving under `/downloads/{filename}`.
- **UPDATED** `44aab1b0-7fe` — Codex was right that the memory is partial, but the suggested correction needed adjustment: current code/env show v3 is enabled, Stage 3 is codex-provider based in this runtime, and there is no `JANE_BRIEFING_MODEL` handling in the code I found.
- **UPDATED** `b983d7f2-b4b` — Actual code confirms the exemplar/model claims, but the memory needs updating for active v3 routing and the live cron vs stale backup distinction.
- **UPDATED** `edc5dd77-b6a` — Confirmed against the actual orchestrator, setup script, docs, and live crontab. Codex was mostly right, but the corrected memory should include the full current JOBS list and note the setup.sh/docs drift.
- **UPDATED** `99c0b500-ab2` — Codex was right: the bridge, config registration, FastMCP tools, AGENTS nearest-2 preflight rule, codex_auto_memory.py, and query_live_memory.py shim all exist; the stale memory only omitted the current preflight path.
- **UPDATED** `79101a69-c26` — Code confirms the multi-user/admin model, but the memory needed the capability nuance for private memory retrieval and should not inherit Codex's unsupported cron/Gemma additions.
- **UPDATED** `e44d09fd-ef8` — Codex was partly right about the path, cron cadence, and intended atomic tracker behavior, but actual code/logs show an import-time IndentationError that prevents the wrapper from recording current attempts.
- **UPDATED** `02389095-cd2` — Live code confirms Codex's v3 routing/classifier/handler/model analysis, but the prior memory was incomplete/stale and Codex's cron-access caveat is no longer true in this environment.
- **UPDATED** `27fda530-892` — Confirmed against actual code and live SQLite schema. Codex was right that the old memory is partially stale: the line numbers changed and the final persistence sentence was incomplete, while the core DB path and turns schema remain correct.
