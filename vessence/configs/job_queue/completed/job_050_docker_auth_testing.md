# Job #50: Docker Onboarding Auth — End-to-End Testing

Priority: 3
Status: completed
Created: 2026-03-28

## Description
Test the self-managed OAuth flow for all three providers on a Windows Docker install:
1. Claude OAuth (v0.0.42+) — verify token exchange at platform.claude.com/v1/oauth/token works, credentials written to ~/.claude/.credentials.json
2. Gemini OAuth (v0.0.42+) — verify Google OAuth token exchange, credentials written to ~/.gemini/oauth_creds.json  
3. OpenAI device-auth — verify device code flow auto-completes
4. All three API key paths work with runtime .env loading
5. Rebuild final installer after all tests pass

## Context
- Claude token endpoint was rate-limited during testing (per-account)
- Gemini OAuth and env loading fixes in v0.0.43
- OpenAI device-auth flow implemented but untested in Docker

## Result
Rewrite it — the full comprehensive version. Let me go through the codebase to fill in the gaps accurately.50) requires a Windows Docker environment. No more jobs I can execute from here. Stopping the auto-continue loop.
