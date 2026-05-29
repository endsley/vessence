# Memory Verification Report — 2026-05-29 02:08

Checked: 20 | Stale: 8 | Fixed: 8 | Deleted: 0 | Errors: 0 | Skipped recent: 178

- **UPDATED** `0cbb3096-6c5` — Codex is right: repo search found no code implementing this guidance; the only Northeastern hit is unrelated course-context text in agent_skills/edu_homework_audit.py. Official Registrar/ITS pages still confirm the guidance, and the original memory is truncated.
- **UPDATED** `e9705c60-0d2` — Confirmed against ~/code/chieh_class_v2/scripts/run_dev_local.sh; Codex was right that the old memory was truncated/inexact about the Google OAuth secrets.
- **UPDATED** `e365d3f2-969` — Confirmed from the hook, Claude settings, prompt list, and runner code. Codex was right: architecture/path claims are current, but the dedupe claim is stale because the status values do not match.
- **UPDATED** `740dc143-e91` — Code and live gcloud/curl checks confirm the service, domain mapping, DB, /login, and /health facts; the original exact cutover timestamp is not established by code and the memory is truncated at `Sour`.
- **UPDATED** `2ac56219-976` — Actual code confirms Codex's partial verdict: v2 merges resolved markers into FIFO persistence, v3 creates resolve_pending_action markers but persists only result.structured in stage2 paths, and TODO parsing still treats 'add an item to urgent' as literal item text.
- **UPDATED** `ae21d358-1a9` — Confirmed against current code; Codex was right that the original memory was truncated and needed the active model-selection details corrected.
- **UPDATED** `ee830a4f-965` — Codex was right: the stored memory is truncated and needs the spec-only status plus the Vessence marketplace vs Facebook Marketplace distinction.
- **UPDATED** `297ceaab-92d` — Confirmed from jane/config.py, actual test_code/ and tests/ listings, TESTS.md, and generate_test_registry.py. The stale part is relying on the current TESTS.md file list.
