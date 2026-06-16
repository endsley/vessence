# Memory Verification Report — 2026-06-16 02:27

Checked: 14 | Stale: 9 | Fixed: 9 | Deleted: 0 | Errors: 0 | Skipped recent: 237

- **UPDATED** `ef78f2aa-91f` — Code and current cached/exported June 2026 Ariel artifacts confirm the architecture and show invoice 6788 excluded $26.56, not 6.5.
- **UPDATED** `d83ab134-93a` — Code confirms the UI, endpoint, table fields, and total-income ordering, but the old source claim is stale: run_income_product_sales_report aggregates saved practitioner report CSVs/fallbacks/manual reconciliations, not one clinic-level AcuBliss Product report.
- **UPDATED** `398b73f7-b00` — Verified against /home/chieh/code/waterlily/scripts/backup_waterlily_history.py, live crontab/config docs, and /home/chieh/ambient/vessence-data/logs/waterlily_history_backup.log; the old last-successful-backup claim is stale.
- **UPDATED** `9ecfcc9d-704` — Confirmed against /etc/fstab, the backup script, and the backup log; Codex was right that the existing memory is only partially wrong because the snapshot path is truncated.
- **UPDATED** `1466722a-a4e` — Current code confirms Codex's main correction: the old 12s timeout is stale and replaced by configurable 2400s default, diagnostics and CODEX_BIN behavior match, and Gemma/qwen facts match. Crontab was readable here and has an unrelated Waterlily backup entry, but the memory itself had no cron claim.
- **UPDATED** `92fc790e-acb` — Confirmed against actual code, service file, py_compile, process cwd/cmdline/env, and timestamps. Codex was right that the timeout/code claims are current and the old restart warning is stale.
- **UPDATED** `032cc1f6-19b` — Checked essence_loader.py, validate_essence.py, essence_runtime.py, jane_web/main.py, and context_builder.py. Codex's PARTIAL verdict is right: the old memory was mostly accurate but omitted essence_runtime/CapabilityRegistry startup usage and needed the conditional ChromaDB detail.
- **UPDATED** `be4829ec-937` — Codex was mostly right and the original memory is truncated/stale, but the actual code adds an important nuance: Android does keep a UI-only chat_history cache, while Jane reasoning context lives in the server SQLite FIFO.
- **UPDATED** `6dbf5f9d-b0d` — Confirmed against jane_proxy routing, standing_codex.py, persistent_codex.py, runtime env, and jane_web logs; the stale part was treating persistent_codex.py as the current default route.
