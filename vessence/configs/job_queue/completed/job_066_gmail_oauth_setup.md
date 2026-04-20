---
Title: Set up Gmail OAuth token for email access
Priority: 3
Status: completed
Created: 2026-04-08
---

## Problem
Jane has full Gmail integration code (read, send, search, delete) but the Gmail OAuth token hasn't been created yet. The token file (`gmail_token.json`) is missing from the credentials directory.

## Goal
Get Gmail working so Jane can read and manage Chieh's email through conversation.

## Current State
- Backend code is complete: `agent_skills/email_tools.py` and `agent_skills/email_oauth.py`
- Google Client ID and Secret are configured in `.env`
- The web sign-in callback already stores Gmail tokens (line 1317-1331 in `jane_web/main.py`)
- Gmail scope (`gmail.modify`) is already requested during web OAuth (line 40 in `vault_web/oauth.py`)
- Missing: `$VESSENCE_DATA_HOME/credentials/gmail_token.json`

## Approach
1. Sign in via Google on the Vessence web UI — the OAuth callback automatically creates the Gmail token
2. Verify token was saved: check `$VESSENCE_DATA_HOME/credentials/gmail_token.json` exists
3. Test email access: `python -m agent_skills.email_tools inbox`
4. If the web sign-in doesn't produce a refresh_token (common if user already authorized the app before), may need to revoke and re-authorize

## Notes
- This requires Chieh to be at a computer with a browser to complete the Google OAuth flow
- The Android app currently doesn't have email tool handlers in ClientToolDispatcher — email works server-side only for now
