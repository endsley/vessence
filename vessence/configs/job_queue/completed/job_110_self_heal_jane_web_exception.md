# Job: Self-heal jane_web: AttributeError at /
Status: completed
Priority: high
Created: 2026-07-04
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260704T133150.109528+0000_jane_web_9e7f53b883cc0c8370daf9c3.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `jane_web`
- Category: `exception`
- Project root: `/home/chieh/ambient/vessence`
- Fingerprint: `9e7f53b883cc0c8370daf9c3`
- Request path: `/`

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260704T133150.109528+0000_jane_web_9e7f53b883cc0c8370daf9c3.json` and the relevant service logs.
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
