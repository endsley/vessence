# Memory Verification Report — 2026-06-23 03:25

Checked: 20 | Stale: 16 | Fixed: 14 | Deleted: 0 | Errors: 0 | Skipped recent: 224

- **UPDATED** `5e97ddf0-58d` — Confirmed in accounting.py, the focused regression test, the current Lace May cache row, and income-cache-backfill-verify.json; only the old stale-cache impact note is wrong now.
- **UPDATED** `fe74615e-2fa` — Actual code confirms Codex: fallback uses last_modified_ym <= report_ym, not exactly same-month, and the original memory has a dangling fragment.
- **UPDATED** `83c815d0-60b` — Original test count was stale. Codex was right about the route flag and contract test, but wrong now about the suite failing: the exact command passed with 172 tests.
- **UPDATED** `06f2f3cf-25d` — Confirmed from actual code: email_tools/email_oauth/main/jane_proxy match Codex's correction, backend Gmail files are absent, Julia token exists, and no Email Worker fallback was found.
- **KEPT** `eedbf895-387` — Codex was wrong to require a correction: the script matches the memory, and live crontab now verifies the daily 5:00 AM entry with the stated log redirection. The log file itself does not exist yet, but the cron destination is configured.
- **KEPT** `4988623e-143` — Codex was wrong for the current codebase/runtime: the code matches the memory and live crontab now verifies the active 0 5 * * * schedule and stated log path.
- **UPDATED** `073e1ce0-553` — Actual code and live crontab confirm the Nutricost-specific daily Gmail job; the old memory's generic future expansion/add-other-deals framing is not represented in current code.
- **UPDATED** `b983d7f2-b4b` — Checked the referenced source, service env file, and live /proc env. Codex was right that the Chroma details are accurate and the memory was truncated/misleading about primary routing; main.py routes v3 first and does not use JANE_USE_V2_PIPELINE for the primary chat endpoints.
- **UPDATED** `edc5dd77-b6a` — Actual code confirms the script, authoritative JOBS list, and current job order; configs/crontab_backup.txt and live crontab both contain the 1:00 AM entry. The stored memory is stale/truncated, and Codex's live-crontab limitation no longer applies.
- **UPDATED** `99c0b500-ab2` — Codex was right: the config, MCP bridge code, and AGENTS memory rules match the verdict, and the existing memory is truncated at the broader-memory rule.
- **UPDATED** `79101a69-c26` — Confirmed against `jane_web/main.py`, `agent_skills/user_manager.py`, `memory/v1/add_fact.py`, and `vault_web/auth.py`; Codex was right that the visible claims are accurate, but the stored memory is truncated and needs completion.
- **UPDATED** `e44d09fd-ef8` — Codex was right about the tracker path, real config filename, and cron entries, but incomplete: live crontab is verifiable now, and the current sequence file is syntactically broken, so `imports and runs` overstates the actual code state.
- **UPDATED** `02389095-cd2` — The operational claims checked out in main.py, jane_v3/pipeline.py, classifier.py, the user systemd unit, live env, and .env; the stored memory was truncated at pending_action and needed completion.
- **UPDATED** `78c280d2-bc1` — Code and the live SQLite DB confirm the ledger path, turns table, columns, Android session prefix, and helper flags. The old memory was truncated; Codex was mostly right, with the added nuance that --turns N returns N*2 ledger rows.
- **UPDATED** `27fda530-892` — Code confirms Codex's substance: the old memory was accurate but truncated before `archival_state` and omitted the current proxy/show_transcript/shim details.
- **UPDATED** `f8b1f197-8f7` — Codex was right that the memory is partial: the old text is truncated and omits the current v3 Stage 2 ledger path. Code and live DB schema confirm the ledger path, columns, ConversationManager writer, stage3 persistence via jane_proxy, and v2/v3 Stage 2 behavior.
