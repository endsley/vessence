# Memory Verification Report — 2026-07-02 03:00

Checked: 20 | Stale: 11 | Fixed: 11 | Deleted: 0 | Errors: 0 | Skipped recent: 247

- **UPDATED** `71f0adca-e72` — Actual code confirms the OAuth fallback and app-default RA report channel. Current state/logs do not support the claimed RA Gmail send or message id; crontab was readable and reinforces that the channel is not set to email.
- **UPDATED** `f1754f9f-0b7` — Original 2-day claim is stale. Codex was right about the code default/no internal 2pm gate, but wrong about current live crontab: it now runs daily at 14:00 EDT with --send-report-now.
- **UPDATED** `7556a72f-52d` — Actual code, lsblk/findmnt, live crontab, log grep/tail, and snapshot directory listing confirm the memory was stale/incomplete; Codex was right but omitted the newer 2026-07-02 snapshot.
- **UPDATED** `ef78f2aa-91f` — Verified against the current code. The core behavior is accurate, but the old memory is stale because report orchestration and helpers are now split across accounting_income_report, accounting_income_products, accounting_income_charges, and accounting_income_invoice_charge_audits.
- **UPDATED** `398b73f7-b00` — Confirmed against the backup script, documented cron files, live crontab, existing paths, and backup log; only the truncated mount path and stale date needed correction.
- **UPDATED** `9ecfcc9d-704` — Confirmed against /etc/fstab, the backup script, the backup log, and the existing snapshot directory; the stale part was the truncated snapshot path.
- **UPDATED** `1466722a-a4e` — Confirmed against current code: jane.py is absent/untracked, the Jane spawn-timeout symbols are absent, and the Gemma/Ollama receipt-enrichment settings and non-streaming /api/chat request match the suggested correction.
- **UPDATED** `92fc790e-acb` — Codex was right: direct code and service-file checks confirm backend/jane.py was deleted, the spawn-timeout symbols are gone, current Gemma config lives in backend/app_config.py, and the waterlily-auth service claim is still accurate.
- **UPDATED** `032cc1f6-19b` — Code confirms the active-state part was stale; Codex was mostly right, except list_available is imported but not actually used in jane_web/main.py.
- **UPDATED** `5fbb727b-767` — Confirmed from the repo: `jane_web/main.py` exists and contains the app entrypoint, while there is no repo-root `main.py`; so `main.py` is only valid as a short visible label, not as a repo-relative path.
- **UPDATED** `6dbf5f9d-b0d` — Source confirms the core routing and normalization claims, but the stored memory is truncated and omits the safe/yolo sandbox distinction.
