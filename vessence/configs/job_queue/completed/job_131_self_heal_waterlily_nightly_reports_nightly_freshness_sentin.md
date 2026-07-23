# Job: Self-heal waterlily_nightly_reports: Waterlily nightly report freshness sentinel detected missing verified output
Status: completed
Priority: high
Created: 2026-07-21
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260721T143001.365465+0000_waterlily_nightly_reports_78876a298d77079793495c98.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `waterlily_nightly_reports`
- Category: `nightly_freshness_sentinel`
- Project root: `/home/chieh/code/waterlily`
- Fingerprint: `78876a298d77079793495c98`
- Request path: ``

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260721T143001.365465+0000_waterlily_nightly_reports_78876a298d77079793495c98.json` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## LLM fallback policy
- Try Codex/OpenAI first.
- If Codex is unavailable, token-full, quota-limited, timed out, or otherwise fails, try Claude Code next.
- If both Codex and Claude Code fail for a critical repair, queue a Vessence repair-failure notice and keep the durable retry active.
- Do not fall back to another model family for a critical repair without an explicit review.
- Record only the runner/provider outcome needed to continue the safe repair flow.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.

## Result
Automatic repair completed after a fresh Waterlily nightly report was verified.