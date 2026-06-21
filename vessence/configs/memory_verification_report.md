# Memory Verification Report — 2026-06-21 02:34

Checked: 20 | Stale: 10 | Fixed: 10 | Deleted: 0 | Errors: 0 | Skipped recent: 224

- **UPDATED** `00b6964f-f83` — Confirmed in accounting.py, main.py, and admin_accounting_reconciliation_scripts.html; original overclaimed nearby invoice context and had trailing junk text.
- **UPDATED** `8233574a-5be` — Codex was right: the original memory omitted several current wait_until_safe() callers, while the function locations and listed original callers still match the code.
- **UPDATED** `072972dd-578` — Confirmed in agent_skills/consult_panel.py, CLAUDE.md, configs/Jane_architecture.md, and context_builder/v1/context_builder.py. The original memory was mostly right but incomplete because it omitted the standing-brain exclusion and was truncated.
- **UPDATED** `27c44480-2e6` — Codex was directionally right that the stored memory should be updated because it is truncated. I verified the actual live crontab, backup crontab, orchestrator source, and logs; unlike Codex's sandbox run, live `crontab -l` was readable here and confirms the single 01:00 entry.
- **UPDATED** `cbba9406-4a9` — Confirmed against AGENTS.md and jane_web/jane_v2/models.py, then imported models with the .env loaded. Codex was right; the stored memory is truncated/incomplete.
- **UPDATED** `e75d7ba1-c90` — Confirmed against `jane/tool_loader.py`, `configs/MCP_SPEC.md`, the live `/home/chieh/ambient/skills` tree, and `load_all_tools(force_reload=True)`. Codex was right; the old memory was truncated/incomplete at the skill list.
- **UPDATED** `4d22a27f-a20` — Confirmed against the code and filesystem. Core path/config claims are correct, but the memory needed the JANE_TOOLS_DIR detail and the transitional context_builder/proxy/model caveats.
- **UPDATED** `0845b572-f6a` — Actual pre-commit KERNEL_PATHS no longer include all of `vessence/android/app/src/`; Codex's corrected path list and partial-enforcement explanation match the current hook and hygiene script output.
- **UPDATED** `0e79d2ac-b55` — Confirmed against current code and env: routing, session scoping, directories, and model configuration still match; stored memory is truncated after `legacy`, so it should be repaired.
- **UPDATED** `02864895-c62` — Confirmed against the code. Codex was right: the core HybridTtsManager flag details are current, but the stored memory was truncated and incorrectly implied briefing/shared summary article reads depend on that flag.
