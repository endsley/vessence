# Job: Self-heal jane_web: OperationalError at /api/essences
Status: incomplete
Priority: high
Created: 2026-06-27
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260627T093624.069403+0000_jane_web_f725fff1cc2f2d124fb2bd72.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `jane_web`
- Category: `exception`
- Project root: `/home/chieh/ambient/vessence`
- Fingerprint: `f725fff1cc2f2d124fb2bd72`
- Request path: `/api/essences`

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260627T093624.069403+0000_jane_web_f725fff1cc2f2d124fb2bd72.json` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.

## Result
Jane web is not running — skipping
