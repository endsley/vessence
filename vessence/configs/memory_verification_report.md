# Memory Verification Report — 2026-06-22 02:56

Checked: 20 | Stale: 16 | Fixed: 16 | Deleted: 0 | Errors: 0 | Skipped recent: 224

- **UPDATED** `adc14588-425` — Confirmed against accounting.py and current cache/export files: product invoice 6202 is excluded from paid income, Madeleine Heckler is matched to DASYS payment-report row 221 for $122.88, and the stored memory lost leading currency digits.
- **UPDATED** `5b0670e6-0e8` — Codex was right: accounting.py has the product-sale exclusion and insurance payment-report fallback logic, and the current Annie April cache/payment reports match the suggested correction; the stored memory is truncated after Madeleine Heckler.
- **UPDATED** `0b0896df-9a4` — Verified against `configs/MCP_SPEC.md`, `jane/tool_loader.py`, `intent_classifier/v1/gemma_router.py`, `jane_web/jane_v2/models.py`, env settings, and the live skills tree. Codex was right that the old memory was truncated/partial.
- **UPDATED** `6d032384-520` — Codex was right that the memory is partial and truncated; code confirms server TTS is disabled and the shared-article/briefing paths need the newer SummaryReaderActivity and direct AndroidTtsManager nuances.
- **UPDATED** `a377227d-b22` — Codex was right: the original memory is truncated at ClientToolDis and omits the current SmsSyncManager/synced_messages/read_messages DB path confirmed in code.
- **UPDATED** `8ff0667e-46c` — Confirmed against jane_web/main.py, jane_web/jane_v3/pipeline.py, intent_classifier/v3/classifier.py, intent_classifier/v2/classifier.py, jane_web/jane_v2/models.py, Android chat code, configured .env, and the live process env. Codex was right that the old memory is substantively correct but truncated at an invalid path.
- **UPDATED** `81ce9c38-874` — Confirmed in the actual code. The memory is only stale because the final file path is truncated to jane_web/jane_v2/classes/music_play/h; the real file is handler.py.
- **UPDATED** `8c7cda38-d7f` — Codex was right: the original memory is substantively accurate but truncated after the registry dispatch claim; code and env confirm the completed version.
- **UPDATED** `ce56ca65-8a9` — Actual code confirms Codex's references and shows the original memory was truncated and missing the pipeline END_CONVERSATION gate-check short-circuit.
- **UPDATED** `2dc3dec8-82f` — Codex was right: the v2 implementation mostly matches the old memory, but current routing prefers v3 when `JANE_USE_V3_PIPELINE=1`, and the v2 doc has stale activation, threshold, and model details.
- **UPDATED** `909d51ad-8ee` — Actual files, download route, and packaged installer scripts confirm Codex's substance; the stored memory is stale only because it is truncated at `Docker Engin`.
- **UPDATED** `6baa82c6-fb9` — Confirmed Codex is right: current handler has a params path with rule-based coherence, legacy LLM fallback, recipient/body checks, and a numeric confidence floor before direct send.
- **UPDATED** `45bd5098-fba` — Code confirms Codex was right: the old text is overbroad because intent_classifier/v2 is not the global active classifier when the v3 pipeline flag is enabled.
- **UPDATED** `44aab1b0-7fe` — Confirmed against models.py, intent_classifier/v3/classifier.py, jane_web/jane_v2/pipeline.py, and daily_briefing/news_fetcher.py; Codex was right that the old memory is truncated and missing the v3 classifier detail.
- **UPDATED** `07c0b045-ba5` — Confirmed from the actual scripts, live crontab, cron docs, job queue filenames, prompt_list.md, and current job_queue.log; the old memory was truncated and missed the job-number parsing bug.
- **UPDATED** `052b10b5-208` — Confirmed against `agent_skills/code_lock.py`; the memory is accurate but truncated at the end.
