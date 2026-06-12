# Memory Verification Report — 2026-06-12 02:51

Checked: 20 | Stale: 13 | Fixed: 13 | Deleted: 0 | Errors: 0 | Skipped recent: 180

- **UPDATED** `6852a648-d83` — Direct inspection confirmed most of Codex's verdict: the memory is stale/truncated at accounting.p and should name backend/accounting.py. Codex was wrong only about this sandbox not being able to read the live crontab; crontab -l succeeded and contains the Waterlily backup line.
- **UPDATED** `2c894759-104` — Verified against /home/chieh/code/waterlily/backend/main.py, backend/templates/admin.html, and .auth/auth.db. Codex was mostly right; the original memory was truncated, over-implied generic options were removed from taxonomy, and the benchmark stats were not found in code/artifacts.
- **UPDATED** `a9313c47-cb6` — Actual code confirms the repo, roles, email worker, signature verification, raw-email storage, and Gemma default. Codex was wrong about 8088/8090 not running in this audit, so the corrected memory keeps the service fact but timestamps it.
- **UPDATED** `ce382ed9-746` — Actual code confirms the storage/model/migration claims, but the old UI placement is stale: the global LaTeX block is before the New module form and module browser, not below a folder-manager link.
- **UPDATED** `31bc71dc-77c` — Code confirms the workflow claims; the stored memory is only stale because it is truncated at the end.
- **UPDATED** `fd478e39-b62` — Confirmed against agent_skills/google_cloud_receipts.py and repo search; Codex was right, and the existing memory is only incomplete because it is truncated at the end.
- **UPDATED** `136c24ff-98c` — Confirmed in code: _default_out_dir() returns ~/Downloads/google_cloud_receipts_<timestamp>/, so the old plain ~/Downloads/ detail was stale; the rest matches the script.
- **UPDATED** `da8286ca-8ab` — Original memory was truncated and slightly mischaracterized topic_memory; code confirms the core provider centralization claims, and live crontab is readable here and matches the backup.
- **UPDATED** `ef1bd7ff-8bd` — Confirmed against q1.py through q10.py, the setup script, and the test file; Codex was right that the old memory's test path was stale/incomplete.
- **UPDATED** `fa8de932-f4d` — Actual q6-q10 code matches Codex's verdict; the stored memory is stale only because q10 is truncated and missing the final gradient-evaluation detail.
- **UPDATED** `f4f3204b-7d1` — Confirmed from actual code and tests; targeted pytest collected and passed 146 tests, so the old 124 count is stale.
- **UPDATED** `1efeb6e4-a73` — Codex was right that the memory was partial/stale: the code constants and architecture still match, but live GCP now shows revision teaching-app-v2-00127-jqx rather than teaching-app-v2-00087-xm5.
- **UPDATED** `dca272e8-326` — Verified against actual files in /home/chieh/code/chieh_class_v2. The substantive claims are current; only the dangling truncated tail "Run lo" is stale/bad.
