# Memory Verification Report — 2026-06-19 02:39

Checked: 20 | Stale: 12 | Fixed: 12 | Deleted: 0 | Errors: 0 | Skipped recent: 219

- **UPDATED** `deaccc58-11e` — Confirmed against accounting.py and the waterlily-appointments-report skill; current code supports the report/API/DASYS/Internal Notes flows but not the old modal/menu/patient-route scraping claims.
- **UPDATED** `73d8ea6f-fcc` — Code confirms the cache fallback and error propagation, but the original historical incident sentence overstated an unproven causal link to the February Kathia report attempt.
- **UPDATED** `24753619-73b` — Codex was right after code inspection and a fresh pytest run: the durable cleanup facts match current code, but 51 tests, the backend PID, and the truncated live-browser fragment are stale or ephemeral.
- **UPDATED** `38aaf277-e2e` — Confirmed from code/config: Codex skills are installed by startup_code/install_codex_skills.py, Vessence tools are loaded from ~/ambient/skills/*/mcp.json by jane/tool_loader.py, and ~/.codex/config.toml only registers jane-memory MCP. Searches found Hugging Face dependency/cache/OmniParser references, but no Hugging Face Discover, ARD, or Spaces discovery tooling.
- **UPDATED** `ecfbb892-6de` — Codex was right: the legacy manifest catalog is still accurate, but the old memory blurred it with the newer jane/tool_loader.py mcp.json tool system.
- **UPDATED** `07699ebf-cd6` — Codex was right: the main architecture claims match the current code and manifests, but the stored memory is truncated at the final sentence and should be replaced with the complete verified version.
- **UPDATED** `813db13b-dd8` — Actual code confirms the core memory, but the original was truncated and imprecise about normalized user IDs, admin authorization, and managed-user scoping.
- **UPDATED** `ab6c6c05-2d0` — Actual code confirms the core claims, but the stored memory is truncated at intent_classifi and needs the complete v3 classifier path/name.
- **UPDATED** `1438587f-d63` — Code confirms the root paths, managed-user vault/memory paths, collection names, upload-to-vault behavior, and file_index_memories metadata indexing; the existing memory is truncated, so it should be repaired.
- **UPDATED** `aa8acff2-18e` — Verified against configs/VESCAB.md, start_agent.sh, agent_skills/essence_runtime.py, live crontab, configs/crontab_backup.txt, configs/CRON_JOBS.md, jane/* shims, jane_web/jane_v2/models.py, and intent_classifier/v1 files. Codex was broadly right; live crontab was readable and showed an extra CRON_JOBS.md drift around auto_pull.
- **UPDATED** `a0f185dc-c42` — Confirmed from the current code: Codex was right that the old memory was truncated and missed the prompt-side/selective enforcement nuance, the broad why-debug trigger, and the streaming-only post-turn flag/correction behavior.
- **UPDATED** `0cc009cd-d02` — Read agent_skills/essence_loader.py; Codex's partial verdict is correct. The stored memory is stale mainly because it is truncated and omits current type_filter/type/has_brain metadata, AMBIENT_BASE defaults, and related registry functions.
