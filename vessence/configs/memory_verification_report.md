# Memory Verification Report — 2026-07-04 02:44

Checked: 18 | Stale: 7 | Fixed: 7 | Deleted: 0 | Errors: 0 | Skipped recent: 252

- **UPDATED** `b7681cc2-e5c` — Codex is right: configs/project_specs/vessence.md confirms the vision text, and current memory code still uses ChromaDB; the stored memory is only truncated.
- **UPDATED** `707720f5-659` — Confirmed against jane/config.py, jane_web/jane_v2/models.py, imports, and direct os.environ path lookups; the stored memory is substantively correct but truncated and should be completed.
- **UPDATED** `813db13b-dd8` — Confirmed in actual code: user_manager.py still has the per-user config and path helpers, while jane_web/main.py uses /api/admin/users routes; the old GET/POST /a endpoint claim is stale/truncated.
- **UPDATED** `ab6c6c05-2d0` — Code confirms the core claims and Codex was right that the original memory is only partial: the final v3 classifier path/name was truncated; I also confirmed the shared Stage 2 Ollama helper uses the same centralized LOCAL_LLM constants.
- **UPDATED** `aa8acff2-18e` — Verified against VESCAB, startup scripts, essence loader/runtime, Jane web startup/API code, compatibility shims, model config, cron docs, crontab backup, and live crontab. Codex was directionally right; the original memory was truncated and missed a few current-code details.
- **UPDATED** `a0f185dc-c42` — Confirmed from `jane_web/verify_first_policy.py`, `jane_web/jane_v2/pipeline.py`, `jane_web/evidence_context.py`, and `jane_web/jane_v3`; original memory was truncated and missed newer helpers plus the v2-only scope.
- **UPDATED** `0f26b102-9f9` — Confirmed Codex was right: current code uses allocations through the report month and marks earlier allocations prepaid; prior patient-payment receipt rows use current-month paid_on allocations for prior invoices; insurance fallback filters by payment post_date/report month.
