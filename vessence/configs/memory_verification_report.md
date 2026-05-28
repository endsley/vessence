# Memory Verification Report — 2026-05-28 02:59

Checked: 20 | Stale: 13 | Fixed: 13 | Deleted: 0 | Errors: 0 | Skipped recent: 160

- **UPDATED** `migrated-lon` — Confirmed in code: jane_proxy persists history/ledger/FIFO, while update_short_term_memory uses short_term_extractor.should_skip and add_fact.py is the direct user_memories writer.
- **UPDATED** `migrated-lon` — Codex was right: the fast path and unresolved-recipient escalation still exist, but the old memory is stale for garbled resolved bodies and for assuming Stage 3 always means Opus.
- **UPDATED** `migrated-lon` — Confirmed in jane_web/jane_v2/classes/todo_list/handler.py: aliases map to Google Doc headers, categories load from todo_list_cache.json, and _speak_category_list filters visible categories with items. Current cache has no students category.
- **UPDATED** `migrated-lon` — Code confirms the todo_list STAGE2_FOLLOWUP abandon path still exists, but clinic_schedules_info now has local Stage 2 loaders, no_stage3=True, privacy=local_only, and v3 privacy gating. The Stage 3 database-query claim is stale.
- **UPDATED** `migrated-lon` — Code audit confirms no Uber integration; only loaded tools are life_librarian, music_playlist, and phone. Codex was right on implementation status but the live memory did include both candidate repos.
- **UPDATED** `migrated-lon` — Confirmed by code search and loader inspection: installed MCPs are phone, life_librarian, and music_playlist; no Uber skill, mcp.json, or Uber API code exists, and MCP descriptors are required for complete Vessence tools.
- **UPDATED** `migrated-lon` — Codex was mostly right after checking the actual Waterlily code, static files, docs, service unit, env names, and live endpoints; the original memory was truncated and needed the live-site verification status updated.
- **UPDATED** `migrated-lon` — Codex was right: the inspected code still has the random fallback, so the old memory claiming a hard startup error is stale.
- **UPDATED** `52c1c4fa-e26` — Codex was right about the code structure, but wrong that the exact DB facts were unverifiable here; the live teaching_app DB on 127.0.0.1:3307 confirms row 36, account id 1, and all three child meeting sections. Update fixes the truncated tail.
- **UPDATED** `7094af79-ac2` — Confirmed in code: Vessence only has generic DS3000 lecture-anchor retrieval, with no Course Daily Topics/doc-ID reference. Vault lecture index and notes show Lecture 2 lacks Frobenius, Lecture 5 is Disney/Pixar, and Frobenius appears in Lecture 6; original memory is truncated and partially wrong.
- **UPDATED** `52643b31-fd0` — Code confirms Codex was right that 0057 is now the Alembic head, but live curl/gcloud verification confirms the revision, health, and 100% traffic claims are still true.
- **UPDATED** `55214a00-a9f` — Confirmed against backend/space_requests.py, backend/main.py, backend/bookings.py, and studio_dashboard.html. The existing memory is mostly right but truncated and missing current approval/waiver/mailto and V1 limitation details.
- **UPDATED** `41f54ac3-ebf` — Verified against the spec, marketing page, Jane web routes, Android Briefing UI, marketplace harvester modules, and live crontab. Codex was right that the memory is partial/truncated and needs disambiguation; live crontab now confirms the marketplace cron entry.
