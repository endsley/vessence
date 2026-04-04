# Job: Use Sonnet for Web/Android Chat — Faster First Token

Status: complete
Completed: 2026-03-24 00:16 UTC
Priority: 1
Model: sonnet
Created: 2026-03-23

## Objective
Route web and Android chat through Claude Sonnet 4.6 instead of Opus for faster response times. CLI stays on Opus for complex code tasks.

## Design
- Add `JANE_BRAIN_WEB_MODEL` env var (default: same as SMART_MODEL)
- In `jane_web/jane_proxy.py`, when building the brain call for web/Android requests, use `JANE_BRAIN_WEB_MODEL` instead of the default model
- CLI sessions continue using Opus (no change)
- Set `JANE_BRAIN_WEB_MODEL=claude-sonnet-4-6` in local .env

## Files Involved
- `jane_web/jane_proxy.py` — model override for web requests
- `jane/config.py` — add JANE_BRAIN_WEB_MODEL config
- `vessence-data/.env` — local override

## Notes
- Sonnet is ~3x faster to first token than Opus
- Quality difference for conversational chat is negligible
- Complex code tasks from web can still be routed to Opus if intent classifier says "hard"
- This is a local .env override — Docker default stays unchanged
