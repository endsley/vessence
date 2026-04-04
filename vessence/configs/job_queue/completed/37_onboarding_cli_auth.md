# Job: Fix Onboarding Auth — CLI Authentication Instead of API Keys

Status: completed
Priority: 1
Model: opus
Created: 2026-03-25

## Problem
The onboarding wizard asks for API keys, but Jane uses CLI binaries (Claude Code, Gemini CLI, Codex) that authenticate via their own login flows. The API key alone may not be sufficient for all providers.

## Current Architecture
- Jane's brain = CLI subprocess (claude / gemini / codex)
- Standing brain spawns: `claude --model X --stream-json` or `gemini` or `codex exec`
- Background tasks use `claude_cli_llm.py` which also calls the CLI
- CLIs authenticate via browser-based OAuth, not API keys

## What Each CLI Needs

### Claude Code
- Primary: `claude login` (browser OAuth via Anthropic account)
- Fallback: `ANTHROPIC_API_KEY` env var works as alternative
- In Docker: the API key fallback is the easiest path

### Gemini CLI
- Primary: `gemini auth login` (Google OAuth)
- Fallback: `GOOGLE_API_KEY` env var
- In Docker: API key fallback works

### Codex (OpenAI)
- Primary: `codex login` (OpenAI OAuth)
- Fallback: `OPENAI_API_KEY` env var
- In Docker: API key fallback works

## Solution
Since all 3 CLIs support API key fallback via env vars, the current approach CAN work — but the onboarding needs to:

1. **Explain clearly** that the user needs an API key from their provider's website
2. **Provide direct links** to get API keys:
   - Claude: https://console.anthropic.com/settings/keys
   - Gemini: https://aistudio.google.com/apikey
   - OpenAI: https://platform.openai.com/api-keys
3. **Set the right env var** based on provider:
   - Claude → `ANTHROPIC_API_KEY`
   - Gemini → `GOOGLE_API_KEY`
   - OpenAI → `OPENAI_API_KEY`
4. **Test the key** before proceeding (call a simple API endpoint to verify)
5. **Install the CLI** on first boot via `install_brain.sh` (already exists in Jane Dockerfile)

## What to change
1. Update `onboarding/templates/setup.html` — step 1 (Choose Brain) should:
   - Show the correct API key link for each provider
   - Label the input correctly (e.g., "Anthropic API Key" not just "API Key")
   - Add a "Get your key" link that opens the provider's key page
2. Update `onboarding/main.py` — `/api/setup` should write the correct env var name based on provider
3. Verify `docker/jane/install_brain.sh` installs the correct CLI on first boot

## Verification
- Onboarding shows correct API key instructions per provider
- Key is saved with the correct env var name
- Jane starts and can respond after onboarding completes
- install_brain.sh installs the correct CLI

## Files Involved
- `onboarding/templates/setup.html`
- `onboarding/main.py`
- `docker/jane/install_brain.sh`
