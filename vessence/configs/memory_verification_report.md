# Memory Verification Report — 2026-06-02 01:32

Checked: 3 | Stale: 2 | Fixed: 2 | Deleted: 0 | Errors: 0 | Skipped recent: 202

- **UPDATED** `833e26a1-513` — Code confirms Codex is right: Vessence has Playwright browser automation, accessibility snapshots, screenshots, and optional traces, but no automatic console/response listeners, HAR validator, axe/pa11y/lighthouse checker, or general client-server contract verifier.
- **UPDATED** `6dbf5f9d-b0d` — Codex was right: source code and the live jane-web process env confirm the memory is stale only because it names a single write root instead of the current multi-root JANE_CODE_WRITE_ROOTS.
