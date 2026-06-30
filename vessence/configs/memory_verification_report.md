# Memory Verification Report — 2026-06-30 02:24

Checked: 20 | Stale: 5 | Fixed: 5 | Deleted: 0 | Errors: 0 | Skipped recent: 223

- **UPDATED** `migrated-lon` — Confirmed in code: v3 routing is enabled by JANE_USE_V3_PIPELINE=1, Stage 2 model resolves to qwen2.5:7b, v3 Stage 2 success paths call _persist_turn_to_fifo and _persist_turn_to_ledger, and there is no jane_web/jane_v2/pipeline._pe function.
- **UPDATED** `63af9718-f11` — Confirmed against `.env`, `jane/config.py`, `jane_web/main.py`, `jane_web/jane_v3/pipeline.py`, `intent_classifier/v3/classifier.py`, and `jane_web/jane_v2/models.py`; Codex was right that the memory was mostly accurate but stale/incomplete about the literal `get_time` shortcut and qwen/Ollama vs Haiku wording.
- **UPDATED** `0cbb3096-6c5` — Repo search found no Vessence classroom-routing implementation; only an unrelated Northeastern mention in agent_skills/edu_homework_audit.py:708. Official Registrar/ITS pages support the routing, but the stored Registrar URL is truncated and 404s.
- **UPDATED** `6e3c1f81-f15` — Confirmed from ChatPreferences.kt/ChatRepository.kt, Jane request logs, and the Android crash incident; the session ID and IN2017/Android 13 evidence are real, but OnePlus8TMO and OnePlus 8T/T-Mobile were not found in current code or runtime evidence.
- **UPDATED** `c73143f4-e15` — Actual code confirms the old memory was partial: the core pipeline is still right, but current report generation also uses product-sales exports, invoice charge audits, patient internal notes, and monthly DASYS insurance payment report rows.
