# Memory Verification Report — 2026-07-21 01:35

Checked: 40 | Stale: 18 | Fixed: 18 | Deleted: 0 | Errors: 0 | Skipped recent: 138

- **UPDATED** `acccce19-73d` — Confirmed in migrations 0032/0033/0034/0048, app/db/models.py, app/problems/base.py, and app/services/prompts.py; the original DB-only/current-runtime wording is stale.
- **UPDATED** `ce382ed9-746` — Actual code confirms the architecture; only the UI template path was stale: _modules_pane is absent and _modules_panel.html is current.
- **UPDATED** `fd478e39-b62` — Verified against agent_skills/google_cloud_receipts.py and agent_skills/google_cloud_receipt_utils.py; Codex was right that the existing memory is accurate but truncated/incomplete.
- **UPDATED** `136c24ff-98c` — Code confirms the workflow and Codex's stale verdict: the stored memory is truncated at the default output detail, and validate_receipt_request requires either count or at least one date bound.
- **UPDATED** `da8286ca-8ab` — Confirmed from jane/config.py, /home/chieh/ambient/vessence-data/.env, memory/v1/janitor_memory.py, jane/automation_runner.py, and agent_skills/claude_cli_llm.py. The stale part was JANE_BRAIN=codex; live .env now has JANE_BRAIN=openai.
- **UPDATED** `ef1bd7ff-8bd` — Confirmed from actual q1.py–q10.py: Q1–Q9 are two-entry vectors, but q10.py returns answer_type="number" with scalar solution=derivative.
- **UPDATED** `fa8de932-f4d` — Confirmed from q6.py through q10.py: Q6–Q9 still match, but Q10 is now a chain-rule-along-a-parameterized-path numeric derivative, not constrained maximization.
- **UPDATED** `dca272e8-326` — Confirmed from actual code: attempts.py imports REGISTRY only, not problem_sort_key; the old memory was truncated and partially wrong.
- **UPDATED** `e3bd58d1-099` — Verified the actual q1.py-q16.py code; Codex was right and the existing memory is truncated after CommonProbDi.
- **UPDATED** `314ba95a-836` — Verified current code: deep-link logic is in app/static/admin-home.js with consumedHash/hashchange handling; app/templates/admin/home.html only loads that script, and module cards still use id="module-{{ m.id }}".
- **UPDATED** `8f16fbf6-501` — Confirmed run_dev_local.sh and the systemd unit match the memory except the enabled symlink path; the actual symlink includes the -dev.service suffix.
- **UPDATED** `310bdda4-225` — Codex was right: README and cloud scaling scripts match the infrastructure claims, and app/routers/student.py plus app/services/student_attempt_flow.py implement owned unfinished assignment-attempt deletion while rejecting finished attempts.
- **UPDATED** `migrated-lon` — Codex was broadly right after code inspection; I corrected route attribution and public asset wiring details.
- **UPDATED** `migrated-lon` — Codex was right: `/admin/jane/*` is gone, but current watchdog/self-healing code still invokes Codex/Claude in constrained failure paths, while Gemma receipt enrichment uses local Ollama.
- **UPDATED** `migrated-lon` — Confirmed in actual code: load_secret_key is in backend/app_config.py; backend/main.py has no WL_SECRET_KEY/load_secret_key refs; .auth/wl_secret_key and .auth/secrets.env exist. Update needed because the old memory was truncated.
- **UPDATED** `241a6b12-78d` — Confirmed by fetching origin/master and grepping templates/index3.html; production and App Engine routing also match Codex's verdict.
- **UPDATED** `52643b31-fd0` — Verified the repo, README/config constants, Alembic files plus `alembic heads`, and app/routers/health.py; Codex was right that the original memory was only partially wrong because it was truncated.
- **UPDATED** `63af9718-f11` — Read the actual .env and code paths; Codex was right on the visible claims, but the stored memory is truncated after “litera”, so it should be replaced with the complete corrected version.
