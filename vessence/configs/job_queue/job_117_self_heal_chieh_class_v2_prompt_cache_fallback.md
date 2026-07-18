# Job: Self-heal chieh_class_v2: Prompt cache ignored saved rows due to untracked_legacy_source_prompt; app used source fallback
Status: pending
Priority: high
Created: 2026-07-17
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260717T141601.533744+0000_chieh_class_v2_7682c8090350baa1c1f79437.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `chieh_class_v2`
- Category: `prompt_cache_fallback`
- Project root: `/home/chieh/code/chieh_class_v2`
- Fingerprint: `7682c8090350baa1c1f79437`
- Request path: ``

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260717T141601.533744+0000_chieh_class_v2_7682c8090350baa1c1f79437.json` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## LLM fallback policy
- Try Codex/OpenAI first.
- If Codex is unavailable, token-full, quota-limited, timed out, or otherwise fails, try Claude Code next.
- If Claude Code is unavailable or fails, try Google's Antigravity CLI (`agy`) next.
- Record which runner handled the repair, or all runner failures if none can complete it.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.
