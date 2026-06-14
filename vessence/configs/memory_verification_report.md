# Memory Verification Report — 2026-06-14 02:19

Checked: 20 | Stale: 8 | Fixed: 8 | Deleted: 0 | Errors: 0 | Skipped recent: 203

- **UPDATED** `migrated-lon` — Confirmed against backend/main.py, backend/events.py, backend/bookings.py, backend/space_requests.py, backend/jane.py, local-assets/public.js/eventlist.js/calendar.js, and Vessence cron docs. Codex was substantively right; I adjusted the corrected memory for exact Jane defaults and the event DOM fallback nuance.
- **UPDATED** `migrated-lon` — Confirmed in source: the secret fallback and root-email env mismatch remain, while the public rental/space-request form and backend endpoint now exist.
- **UPDATED** `migrated-lon` — Confirmed in actual code at main.py lines 67-90; existing memory is correct but truncated at the fallback call.
- **UPDATED** `52643b31-fd0` — Confirmed by reading the repo, migration files, alembic heads, health route code, curl health check, and gcloud service describe. The old Alembic head and Cloud Run revision were stale.
- **UPDATED** `63af9718-f11` — Confirmed from jane.config, /home/chieh/ambient/vessence-data/.env, jane_web/main.py, jane_web/jane_v3/pipeline.py, intent_classifier/v3/classifier.py, and legacy v2 files; Codex was right that the old memory describes legacy v2, not the active v3 path.
- **UPDATED** `55214a00-a9f` — Code confirms Codex was right: /api/space-requests is public, bookings uses _require("studio_user"), and role ordering lets root, manager, acupuncturist, and studio_user access it.
- **UPDATED** `41f54ac3-ebf` — Confirmed against the spec and code: the spec still describes paid essence/skill commerce, the shipped marketplace page is static/free sample data, Stripe/payment work exists only in docs/TODOs, and `/api/marketplace` is Facebook Marketplace tooling.
- **UPDATED** `0cbb3096-6c5` — Repo search found no classroom/Registrar/ITS routing code, only an unrelated Northeastern mention in edu_homework_audit.py. Live checks show the classroom page and /types/form/ are valid, while /type returns 404; current Registrar and ITS pages point to the Registrar Service Portal, Student Hub forms, and Classroom Dashboard.
