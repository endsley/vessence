# Memory Verification Report — 2026-07-03 02:21

Checked: 9 | Stale: 5 | Fixed: 5 | Deleted: 0 | Errors: 0 | Skipped recent: 260

- **UPDATED** `90bd494a-c15` — Codex was only partly right: current source is v0.2.99 and has only three OpenWakeWord assets, but the v0.2.91 APK does contain the camera-sync feature strings and the v0.2.90 to v0.2.91 APK size drop is present in the repo artifacts.
- **UPDATED** `ca32e5b0-eb0` — Code confirms the National Grid files, handler, and account links. The original memory was stale because v3 is gated by JANE_USE_V3_PIPELINE, Android only posts to the server stream endpoint, and the non-v3 path can be v2 or legacy depending on JANE_PIPELINE.
- **UPDATED** `bd14389e-cec` — Actual code matches the functional claims, but git log/blame do not support the 2026-06-03 date claim.
- **UPDATED** `deaccc58-11e` — Actual code confirms Codex's wrapper/delegation finding and the original memory is truncated at 'and DA'; I also included currently used enrichment sources visible in accounting_income_report.py and accounting.py.
- **UPDATED** `73d8ea6f-fcc` — Actual code confirms Codex was right: accounting.py now delegates the full report builder to accounting_income_report.py, fresh full report generation omits force_refresh=True, and the cache fallback/_refresh_error/source fields behave as described.
