# Memory Verification Report — 2026-06-24 02:52

Checked: 20 | Stale: 15 | Fixed: 15 | Deleted: 0 | Errors: 0 | Skipped recent: 226

- **UPDATED** `dcf2f212-0ae` — Verified filesystem, skill files, Claude logs, and install_codex_skills.py. The symlink/load claim is current, but the blanket bundled-script/adk-python instruction and installer ownership claim were partially wrong.
- **UPDATED** `3360bc85-083` — Confirmed from the design note, main.py endpoint routing, current vessence-data .env, v3 pipeline/classifier, v2 classifier, and v2 stage1 wrapper; the old endpoint/current-routing claim was stale and incomplete.
- **UPDATED** `054561e1-e57` — Confirmed against the actual repo and live crontab. Codex was mostly right, but the sandbox-specific crontab caveat is not true here, and the memory should distinguish stale docstring text from executable behavior.
- **UPDATED** `e17cda7c-016` — Code confirms the Stage 2 depth, clinic privacy/no_stage3 metadata, and active Stage 1 path; the original final symbol intent_classifier.v2.classifier.s is invalid/truncated.
- **UPDATED** `ead0d5ad-0a7` — Confirmed from version.json, android/app/build.gradle.kts, rg search, and keytool: Codex was right; the stored version and SHA-1 were stale/incomplete.
- **UPDATED** `6e76b008-7f1` — Confirmed from docs, Android detector code, asset listing, git-tracked files, repo-wide search, and SHA-256 hashes. Codex was right that the source v7 backup claim is stale.
- **UPDATED** `ef5612fc-3ee` — Read the actual handler and models code. Codex was right on the architecture; the stored memory is truncated and should be completed.
- **UPDATED** `5001554f-1cc` — Repo files and scripts match the memory, and `crontab -l` now verifies the live entry; update because the stored memory is truncated. Codex was wrong only about live crontab remaining unverified in this run.
- **UPDATED** `1ec8aa82-4b3` — Verified against the actual repo and filesystem. The original memory is mostly correct, but its final sentence is truncated and its GCP-only claim needs to be scoped to production/runtime DB because local/dev MySQL and sqlite test paths still exist.
- **UPDATED** `eef09673-adb` — The paths, imports, Playwright version, browser binaries, and code references check out. Codex was wrong about the current live-launch failure here: direct headless launch and the actual BrowserSessionManager path both succeeded, but the stored memory should be updated because its text is truncated and the verification date is stale.
- **UPDATED** `a04927a6-a64` — Verified against git state and source code; Codex was right that only the HEAD claim was stale while the public rental request flow still matches.
- **UPDATED** `5d6c603e-98e` — Actual code confirms Codex's verdict; the stored memory is truncated and should be replaced with the complete corrected version.
- **UPDATED** `331fa4d4-25e` — Codex was right that the code-backed claims still hold and the old Cloud Run revision fragment is stale; I verified the current live revision with gcloud.
- **UPDATED** `52389d73-e52` — Code confirms the visible claims, but the stored memory is truncated after "only the per-", so it should be updated with the complete text.
- **UPDATED** `acacc0e7-035` — Verified against the current repo: Codex's correction matches the source, and the existing memory is truncated/incomplete at q3-q7.
