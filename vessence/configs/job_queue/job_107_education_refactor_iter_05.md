# Job: Education / teaching app iterative refactor 5/5
Status: incomplete
Priority: medium
Created: 2026-06-30
Tags: scheduled-refactor, education, iteration-5

## Objective
Use the refactoring skill/workflow to answer: what other refactoring can we do to further speed up this codebase and enhance readability? Then implement exactly one small, behavior-preserving refactor slice in `/home/chieh/code/chieh_class_v2`.

This is iteration 5 of 5 for `education`. The goal is to build on whatever previous iterations already refactored, not repeat them.

## Context
- Project: Education / teaching app
- Project root: `/home/chieh/code/chieh_class_v2`
- Refactor focus: teaching app page load speed, FastAPI/HTMX route structure, data access, template organization, tests, and readability.
- Chieh requested an hourly, bounded, iterative refactor loop across Waterlily, the education project, and Vessence.
- Read the project's local instructions and `REFACTORING.md` first when present.
- Check `git status --short` before editing. Treat existing unrelated dirty files as Chieh's work; do not revert or stage them.
- Before source edits, acquire the project's code edit lock with `agent_skills.code_lock`.
- Prefer one coherent slice that improves speed, page/load time, developer reading speed, or module boundaries.
- Preserve behavior, public routes, data formats, report output, cache schemas, and UI text unless a proven bug requires a narrow fix.
- If no safe slice exists, document the blocker in the project refactor journal and stop cleanly.

## Steps
1. Read current project instructions, architecture/refactor notes, and the relevant modules.
2. Rank the next safe refactor candidates for this project.
3. Choose one small slice with low behavior risk and meaningful readability or speed impact.
4. Implement the slice behind compatibility wrappers when needed.
5. Run focused tests plus the strongest practical broader test command.
6. Update the project refactor journal with scope, files changed, behavior preserved, verification, and remaining follow-up.
7. If edits were made and tests passed, commit only the intended project changes locally. Do not push unless credentials and project policy make that explicitly safe.

## Verification
- Report the exact tests or checks run.
- If any test is unavailable or blocked, state the blocker and run the strongest focused substitute.
- Confirm unrelated dirty files were left untouched.

## Files Involved
- `/home/chieh/code/chieh_class_v2`
- Project refactor journal, usually `/home/chieh/code/chieh_class_v2/REFACTORING.md`
- Vessence job queue file `job_107_education_refactor_iter_05.md`

## Result
Jane web is not running — skipping
