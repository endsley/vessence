# Job: Self-heal waterlily_nightly_reports: income_product_sales failed: AccountingError: AcuBliss product-sales source provenance contract failed; cached income re
Status: in_progress
Priority: high
Created: 2026-07-19
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260719T040057.339192+0000_waterlily_nightly_reports_91d66175b62fb1b413c98900.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `waterlily_nightly_reports`
- Category: `direct_vendor_ui_full_regeneration_failure`
- Project root: `/home/chieh/code/waterlily`
- Fingerprint: `91d66175b62fb1b413c98900`
- Request path: `/admin/accounting/income/product-sales`

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260719T040057.339192+0000_waterlily_nightly_reports_91d66175b62fb1b413c98900.json` and the relevant service logs.
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
Automatic critical repair is retrying until a fresh Waterlily nightly report verifies successfully.