# Memory Verification Report — 2026-07-01 02:39

Checked: 20 | Stale: 11 | Fixed: 10 | Deleted: 0 | Errors: 0 | Skipped recent: 230

- **UPDATED** `e2d28b52-c41` — Code, imports, doc-drift parser/tests, and git refs confirm the refactor claims; 21 relevant focused tests pass. Codex was wrong about current GitHub access still being unclean.
- **UPDATED** `53d9824a-2f1` — Actual code, CRON_JOBS.md, live crontab, state.json, and run logs confirm Codex was mostly right. The old memory was stale because the final recommendation path was truncated and it omitted the recent Codex argument-length fallback; Codex's note that live crontab was unreadable is not true in this environment because `crontab -l` was readable and shows the active job.
- **UPDATED** `86f8e8fb-ca6` — Confirmed from the script, CRON_JOBS.md, scheduler state/logs, and current crontab that the only stale part was minute 7; the actual completed schedule was minute 52.
- **KEPT** `46d29735-929` — Codex was wrong to require a correction: commit 0a57ed4 is on origin/master, the implementation/wrapper/docs match the memory, and the live crontab confirms the 10 5 * * * schedule.
- **UPDATED** `fdb2813d-69f` — Confirmed in the live script: DEFAULT_OUT_DIR is /home/chieh/code/waterlily/.auth/download_artifacts and --out-dir defaults to it; no Downloads fallback found.
- **UPDATED** `ce89971f-01c` — Confirmed in startup_code/bump_android_version.py, android/app/build.gradle.kts, and jane_web/main.py; the original memory is accurate but truncated and missing fallback behavior.
- **UPDATED** `ae21d358-1a9` — Codex was right: the stale part is the validator claim. Actual validate_manifest allows preferred_model: null while requiring the key and validating object subfields only when present as an object.
- **UPDATED** `bd704a5d-98b` — Code confirms the model-config facts, runtime v3 enablement, and shared imports. The stale part is that the original memory treated v2 gate/continuation checks as active in the current v3 pipeline; they still exist but are skipped by active v3 routing.
- **UPDATED** `046fc30a-7ec` — Confirmed against configs/VESSENCE_SPEC.md, jane_web/main.py, agent_skills/essence_loader.py, vault_web/static/essences.html, and Android Essences UI/repository code. Codex was right that the stored memory is truncated and partially incomplete.
- **UPDATED** `473c4e96-5ac` — Confirmed against README.md, CLAUDE.md, app code/config, and git state; Codex was right that the old current-checkout portion was stale/incomplete.
- **UPDATED** `00698b9a-68f` — Confirmed in jane/config.py, jane_web/jane_proxy.py, llm_brain/v1/standing_codex.py, jane/persistent_codex.py, and llm_brain/v1/persistent_codex.py; the old memory was truncated and overstated JANE_CODE_WRITE_ROOTS as the only standing Codex write-root source.
