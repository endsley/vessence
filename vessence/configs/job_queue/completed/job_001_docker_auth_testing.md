# Job #1: Docker Onboarding Auth — End-to-End Testing

Priority: 3
Status: blocked
Blocked on: Claude OAuth rate limit (per-account), Windows Docker test machine needed
Created: 2026-03-29

## Description
Test the self-managed OAuth flow and API key paths for all three providers on a Windows Docker install.

### Test matrix:
1. **Claude OAuth** — verify token exchange at platform.claude.com/v1/oauth/token works (was rate-limited, should be cleared by now), credentials written to ~/.claude/.credentials.json
2. **Claude API key** — verify ANTHROPIC_API_KEY written to .env and picked up at runtime
3. **Gemini OAuth** — verify Google OAuth token exchange, credentials written to ~/.gemini/oauth_creds.json
4. **Gemini API key** — verify GOOGLE_API_KEY + GEMINI_API_KEY written to .env, settings.json created with gemini-api-key auth type, trustedFolders.json created
5. **OpenAI device-auth** — verify device code flow auto-completes, device code displayed on onboarding page
6. **OpenAI API key** — verify OPENAI_API_KEY written to .env

### Known issues to verify fixed:
- Gemini CLI needs settings.json with `security.auth.selectedType: "gemini-api-key"` (added in install_brain.sh)
- Gemini CLI needs trustedFolders.json to skip interactive trust prompt (added in install_brain.sh)
- Runtime .env loading for API keys written after container start
- Auth toggle visible for all providers (was hidden when presetBrain was set)

### After all tests pass:
- Rebuild final installer package
- Update version numbers
