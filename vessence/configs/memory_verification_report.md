# Memory Verification Report — 2026-07-22 01:26

Checked: 40 | Stale: 14 | Fixed: 14 | Deleted: 0 | Errors: 0 | Skipped recent: 158

- **UPDATED** `0cbb3096-6c5` — Repo search found no Northeastern classroom-routing code; only unrelated Northeastern Concur and education audit references. Official pages confirm the old Registrar URL is truncated/404, the Classroom Management URL is current, Class Section Updates live under Class Information, and classroom technology/Dashboard support routes through ITS/Tech Service Portal and Academic Technologies.
- **UPDATED** `8977a372-aa4` — Confirmed in code: main.py delegates to instant_command_response, and instant_commands.py contains the cron phrase matching and raw code-block formatting.
- **UPDATED** `c73143f4-e15` — Confirmed from actual code: Codex was right that the old memory omitted current package, product, invoice-audit, DASYS payment/claim, patient-note, and pending-insurance processing.
- **UPDATED** `53d9824a-2f1` — Verified the script, configs/CRON_JOBS.md, and live crontab. Codex was right: the only stale part was the cadence, which is daily at 2 PM ET, not every two hours.
- **UPDATED** `7c59ae31-e33` — Confirmed in code and active crontab: agent_skills/ra_research_cron.py regenerates the plan, but crontab has 0 14 * * *, not every 2 hours.
- **UPDATED** `86f8e8fb-ca6` — Actual code confirms the scheduler, project roots, MAX_ITERATIONS=5, and self-disable logic; persisted state and crontab confirm the runs, but the original memory cites logs that are absent and ends mid-phrase.
- **UPDATED** `e0f336e1-0db` — Confirmed against crontab, agent_skills/nutricost_deal_monitor.py, gmail_cleanup_decisions.py, and gmail_cleanup_queries.py; Codex was right that the medical/financial exclusion is not implemented and old-unread cleanup is broad.
- **UPDATED** `46d29735-929` — Confirmed in actual code: the wrapper now sets max-delete=1000, stale-days=21, and passes --include-protected; the Python code disables keep_titles when that flag is present. Cron still runs at 5:10 AM and commit 0a57ed4 is on origin/master.
- **UPDATED** `ce89971f-01c` — Checked the script, Gradle config, main.py, and release_downloads.py. Codex was right that main.py no longer has literal Android fallback constants; release handling moved to release_downloads.py.
- **UPDATED** `bd704a5d-98b` — models.py, v3 classifier, warmup/heartbeat code, $VESSENCE_DATA_HOME/.env, and the live jane_web process env confirm Codex’s partial verdict; the old memory was truncated/stale about runtime env.
- **UPDATED** `71f0adca-e72` — Confirmed in code and token metadata; original had an incomplete unverifiable tail fragment and used plural scopes though the token key is singular scope.
- **UPDATED** `4363c5ec-28f` — Code confirms the RA cron, app-default delivery, announcement behavior, endpoint, polling worker, and ReportReaderActivity integration; only the Android version was stale: version.json is 0.2.102, code 333.
- **UPDATED** `f1754f9f-0b7` — Verified the script defaults and should_send_report logic, active crontab line, system timezone, and configs/CRON_JOBS.md; Codex was right that the memory was partially stale.
- **UPDATED** `47709484-70b` — Current code confirms the helper modules/import aliases; git history shows the main helper commit on 2026-07-02 and invoice grouping on 2026-07-04. The test/review details are corroborated by REFACTORING.md, not by code.
