# Memory Verification Report — 2026-06-29 02:47

Checked: 20 | Stale: 9 | Fixed: 9 | Deleted: 0 | Errors: 1 | Skipped recent: 221

- **UPDATED** `4c1fe65b-dfa` — Confirmed against jane_proxy, standing_codex, persistent_codex, and memory_retrieval; the old memory was overbroad about always prepending the block and was truncated.
- **UPDATED** `e3bd58d1-099` — Verified against the actual q1-q16 source files, problem_registry.py, app/main.py, and prompts.py. Codex was right that only the trailing incomplete prompt-metadata claim was stale/partial.
- **UPDATED** `8f16fbf6-501` — Confirmed from scripts/run_dev_local.sh, app/main.py, the systemd unit file, and the enabled-unit symlink. The old memory is truncated at 'with Exec' and should be replaced.
- **UPDATED** `310bdda4-225` — Confirmed against the actual chieh_class_v2 README, gcloud scaling service, exam scripts, student router, and homework template. Codex was right; the old memory is accurate but truncated at app/templ.
- **UPDATED** `migrated-lon` — Code confirms Codex was mostly right and the memory is stale due to the truncated `intent_ki`; I removed the unsupported claim that classifier params include confidence in the schema.
- **UPDATED** `migrated-lon` — Confirmed against Waterlily source, routes, config, local assets, templates, docs, live crontab, and backup logs; Codex was right that the Jane/admin LLM/qwen/admin space-request parts were stale.
- **UPDATED** `migrated-lon` — Confirmed in code: Vessence still has the Codex bypass runner, but Waterlily ARCHITECTURE.md/AGENTS.md forbid outside-provider LLM runtime paths, backend routes/templates have no /admin/jane/Admin Jane surface, and receipt enrichment calls local Ollama/Gemma.
- **UPDATED** `migrated-lon` — Confirmed against the actual Waterlily source, systemd service, and redacted env-key checks; Codex's PARTIAL verdict and suggested correction are accurate.
- **UPDATED** `migrated-lon` — Confirmed from actual app_config.py and main.py; the old memory had the location, token length, and fallback persistence wrong.
