# Job #72: Web Automation Skill — Spec Only

Status: pending
Priority: 3
Created: 2026-04-17

## Summary

Design and write a full spec for a new Jane skill: browser automation using Playwright + CDP. This job is SPEC ONLY — no implementation until the user approves the spec.

## Requirements (from conversation)

Two modes:
1. **Ad-hoc**: User tells Jane "go to this site and do X" — Jane navigates, interacts, and reports back in real time.
2. **Saved workflows**: User walks Jane through a task once, Jane saves the steps as a replayable script, triggerable by name.

Tech stack:
- Playwright (primary high-level interface)
- Chrome DevTools Protocol (CDP) for advanced tasks: network interception, cookie manipulation, JS injection
- OmniParser/OmniTool (already in repo) as potential visual fallback for complex sites

## Spec should cover

- Architecture: where the skill lives, how it integrates with Jane's pipeline (intent classification, stage2 handler)
- Playwright setup and browser lifecycle management (headless Chromium, persistent sessions vs ephemeral)
- Ad-hoc mode: how Jane reasons about page structure, takes screenshots for verification, handles errors
- Saved workflow mode: storage format, replay engine, how to handle site changes/breakage
- CDP integration: which advanced features to expose, security considerations
- Auth/session management: how to handle logins, cookies, 2FA
- Safety: what sites/actions to restrict, confirmation before sensitive actions (purchases, form submissions)
- Interaction model: what the user sees during automation (progress updates, screenshots, results)

## Deliverable

A markdown spec document in configs/ that Chieh can review and approve before any code is written.

## Constraints

- Do NOT install Playwright or write any code
- Do NOT start implementation
- Spec only — present to user for approval
