# Job: Web Jane Outage Audit
Status: complete
Priority: 2
Created: 2026-03-24

## Objective
Audit the web Jane stack to identify all failure modes that could cause an outage, then post the findings as an entry in the Work Log essence.

## Context
Jane has had prior outages traced to stream teardown gaps, missing env files, and brain subprocess timeouts. The web stack spans several components:
- `jane_web/` — frontend (served HTML/JS/CSS)
- `jane/` — backend proxy (`jane_proxy.py`, session handling)
- `amber_proxy.py` — Amber bridge
- `main.py` — main FastAPI server
- `auth.py`, `oauth.py` — auth layer
- systemd services: `jane-web.service`, `amber-brain.service`
- ChromaDB for memory
- Claude CLI subprocess (`agent_skills/`)

Reference architecture: `configs/Jane_architecture.md`, `configs/memory_manage_architecture.md`

## Pre-conditions
- Access to all source files in `$VESSENCE_HOME`
- Access to systemd service definitions
- Access to logs if available

## Steps
1. Read `jane_proxy.py` — identify: missing error handling, uncaught exceptions, timeout gaps, stream teardown issues
2. Read `main.py` — identify: unhandled routes, missing auth guards, startup failures
3. Read `auth.py` and `oauth.py` — identify: token expiry edge cases, session invalidation gaps
4. Check systemd service files for `jane-web.service` and `amber-brain.service` — identify: missing restart policies, env file dependencies, ordering issues
5. Check `agent_skills/` entrypoints — identify: subprocess timeout handling, error propagation
6. Check ChromaDB connection handling — identify: no-connection fallbacks, timeout handling
7. Cross-reference with known past outages (stream teardown at `2026-03-20`, env file missing for `amber-brain.service`)
8. Compile a ranked list of outage risks: severity (critical/high/medium), likelihood, and recommended fix
9. Post findings to the Work Log using the Work Log tool/API:
   - Use `save_briefing()` or the appropriate Work Log write mechanism
   - Format: timestamp + "Web Jane Outage Audit" header + ranked risk table + recommendations

## Verification
- Audit report posted and visible in Work Log
- All findings are actionable (each has a recommended fix)
- At least the known past failure modes are covered

## Files Involved
- `/home/chieh/ambient/vessence/jane_proxy.py` (or equivalent)
- `/home/chieh/ambient/vessence/main.py`
- `/home/chieh/ambient/vessence/auth.py`
- `/home/chieh/ambient/vessence/oauth.py`
- `/home/chieh/ambient/vessence/agent_skills/` (entrypoints)
- Systemd service files for `jane-web` and `amber-brain`
- `configs/Jane_architecture.md`

## Notes
- Past outages: stream teardown hole (2026-03-20), amber-brain.service missing env file (March 17 outage)
- Work Log write mechanism: check if there's a `save_entry()` or similar in the work log essence tools, or use the briefing save path
- Do NOT fix issues during the audit — report only. Create follow-up job specs for any critical fixes found.
