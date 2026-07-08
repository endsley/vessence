# Memory Verification Report — 2026-07-08 03:34

Checked: 28 | Stale: 16 | Fixed: 16 | Deleted: 0 | Errors: 1 | Skipped recent: 251

- **UPDATED** `e3b277b6-f2c` — Codex was right on the code and dependency facts, and the original memory is truncated. The only adjustment is that crontab was readable here, so verified cron schedules are included instead of preserving Codex's crontab-access caveat.
- **UPDATED** `7a88cd4e-949` — Read the current Waterlily code and tests. Codex was right that the memory is partial: it is truncated at "hardened Fa", includes an unverified superseding claim, and omits several current hardening details.
- **UPDATED** `b72e44f8-f67` — Code and REFACTORING.md confirm Codex's main findings; the stored memory is truncated and missing the 2026-07-08 follow-up passes.
- **UPDATED** `589e9d0b-dd0` — Actual code confirms the frontend claims, but the memory is stale because backend/main.py now has public metrics storage and space-request honeypot handling; the original text was also truncated.
- **UPDATED** `5e97ddf0-58d` — Confirmed from actual code and focused tests; Codex was right that the memory's core claim is accurate but the regression test name was truncated.
- **UPDATED** `fe74615e-2fa` — Verified against the current code and focused tests; Codex was right that the code claim still holds, but the old cache timestamp/date claim is stale because current 2025-12 Ariel/Kathia cache files have generated_at/mtimes on 2026-07-04.
- **UPDATED** `83c815d0-60b` — Original memory was stale: the GET cache route now disables source-link backfill and explicit backfill moved to the POST route. Codex was partly right about the code, but its pytest failure claim is now wrong; the exact command passed.
- **UPDATED** `06f2f3cf-25d` — Confirmed in code: Codex was right that the old memory was mostly correct but missed the server_email_tools delegation layer and helper module.
- **UPDATED** `4988623e-143` — Codex was right that the old memory is partial: the script still does the Nutricost 30% deal monitor, but the current code also performs broader Gmail cleanup passes.
- **UPDATED** `073e1ce0-553` — Codex was right that the old memory was incomplete because the script now does broader Gmail cleanup. Its live-crontab caveat is stale: crontab -l succeeded here and confirms the 5:00 AM job.
- **UPDATED** `edc5dd77-b6a` — The memory was truncated after `Current`; the script, JOBS list, job order, Python path, backup cron, and live crontab were verified from the actual files/runtime. Codex was mostly right, but its live-crontab permission caveat is not true in this run.
- **UPDATED** `99c0b500-ab2` — Verified the live config, MCP module, and AGENTS.md. Codex was substantively right; the stored memory is truncated after `lim`, so it should be updated.
- **UPDATED** `79101a69-c26` — Confirmed against actual code. The old memory is partially stale because `_is_user_admin()` in `jane_web/main.py` is now a wrapper; the comparison and managed-user `user_admin` capability check live in `jane_web/user_access.py`.
- **UPDATED** `e44d09fd-ef8` — Code and config claims are confirmed. Codex was right on the source details, but its suggested live-crontab caveat is outdated here because `crontab -l` succeeded and confirms the paused Kathia cron.
- **UPDATED** `78c280d2-bc1` — Confirmed against code and live DB: ledger path/schema and Android ID generation are accurate, show_transcript filters raw jane_android_%, and user_manager can namespace managed-user session IDs. The stored memory was truncated and missed the unmanaged-scope qualifier.
- **UPDATED** `f8b1f197-8f7` — Confirmed against jane/config.py, agent_skills/show_transcript.py, memory/v1/conversation_manager.py, and the live SQLite turns schema; the original memory is substantively correct but truncated after 'with'.
