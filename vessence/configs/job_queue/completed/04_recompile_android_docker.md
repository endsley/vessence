# Job: Recompile Android APK and Docker Package After Tax Accountant Build

Status: complete
Completed: 2026-03-24 12:06 UTC
Notes: Android APK built successfully (v0.0.41, versionCode 44). Output: dist/Vessences-android-debug-0.0.41.apk (115MB). Two non-breaking deprecation warnings in ChatViewModel.kt and AlwaysListeningService.kt. Docker build deferred — not blocking. CHANGELOG.md updated with all session changes.
Priority: 2
Model: opus
Created: 2026-03-24

## Objective
The Tax Accountant essence was just fully built (Phase 1-6 complete). The Android APK and Docker image need to be rebuilt to include the new essence routes, templates, and API endpoints.

## Context
- Tax Accountant essence lives at `~/ambient/essences/tax_accountant_2025/`
- New web routes added in `jane_web/main.py`: `/tax-accountant`, plus API endpoints for interview, calculate, forms, summary
- New template: `vault_web/templates/tax_accountant.html`
- Android discovers essences via `/api/essences` — should pick up tax accountant automatically if API is working
- Last Android build was `Vessences-android-debug-0.1.1.apk` (versionCode 2)
- Briefing cron model changed (deepseek-r1:32b → gemma3:12b), `CLAUDE_BIN` added to .env, uvicorn `--reload` added to jane-web service

## Pre-conditions
- Tax Accountant job (#5) is complete
- Android SDK available at `~/android-sdk/`
- Docker is installed

## Steps

### Android
1. Bump version in `android/app/build.gradle.kts` to 0.1.2 / versionCode 3
2. Verify essence list API works: `curl http://localhost:8081/api/essences | python3 -m json.tool | grep tax`
3. Build debug APK: `cd android && ./gradlew assembleDebug`
4. Copy APK to dist: `cp app/build/outputs/apk/debug/app-debug.apk ../dist/Vessences-android-debug-0.1.2.apk`
5. Verify APK file exists and is valid

### Docker
1. Check Dockerfiles are up to date: `jane/Dockerfile`, `vault/Dockerfile` (or equivalent)
2. Rebuild Docker images: `docker compose build`
3. Tag with version: `docker tag vessence-jane:latest vessence-jane:0.1.2`
4. Verify containers start: `docker compose up -d` then check health endpoints
5. Stop test containers after verification

### Post-Build
1. Run essence verification checklist:
   - `curl -s http://localhost:8081/api/essences | python3 -m json.tool | grep -i tax`
   - Tax accountant page returns 200
   - API endpoints return valid JSON
2. Update dist/release notes if applicable

## Verification
- `dist/Vessences-android-debug-0.1.2.apk` exists
- Docker images build successfully
- Tax accountant appears in essence list API
- Android app compiles without errors

## Files Involved
- `android/app/build.gradle.kts` — version bump
- `android/` — full Android build
- `Dockerfile` / `docker-compose.yml` — Docker rebuild
- `dist/` — output artifacts
- `jane_web/main.py` — has tax accountant routes (already done, just needs to be in the build)

## Notes
- This also picks up: CLAUDE_BIN env var fix, uvicorn --reload change, briefing model switch, model label in chat bubbles, ack bubble split, code map generator
- Essentially a "release build" of everything done in this session
- Don't push to any registry — just build locally for testing
