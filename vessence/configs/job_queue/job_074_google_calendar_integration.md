---
Title: Google Calendar integration — read today's events
Priority: 3
Status: completed
Created: 2026-04-19
Completed: 2026-04-19
Source: user_request
---

## Goal

Let users ask Jane "what's on my calendar today" (or tomorrow, this week, etc.)
and get a spoken summary of their Google Calendar events.

## Context

- OAuth already requests `calendar.events` scope (`vault_web/oauth.py:40`)
- Token storage pattern exists in `agent_skills/email_oauth.py` — same
  pattern can be reused for calendar tokens (they come from the same
  Google OAuth flow, so the existing refresh token already covers calendar)
- The v2 intent classifier pipeline handles routing; a new `read_calendar`
  class is needed in `jane_web/jane_v2/classes/`
- Email integration is the closest reference implementation — it fetches
  data server-side and injects it into the LLM context as `[EMAIL INBOX DATA]`

## Implementation Plan

### 1. Calendar API helper (`agent_skills/calendar_tools.py`)

- Use `google-api-python-client` + `google-auth` (already installed for Gmail)
- Load credentials from the existing Gmail token file (same OAuth grant)
- Functions:
  - `get_todays_events(user_id: str) -> list[dict]` — returns events for today
  - `get_events_range(user_id: str, start: datetime, end: datetime) -> list[dict]`
  - Each event dict: `{summary, start, end, location, description, all_day: bool}`
- Handle token refresh using the existing refresh token flow
- Handle "no token" case gracefully (tell user to sign in via web UI)

### 2. Intent classifier class (`jane_web/jane_v2/classes/read_calendar/`)

- `metadata.py`: classifier examples like "what's on my calendar",
  "do I have any meetings today", "what's my schedule this week",
  "any appointments tomorrow"
- Adversarial examples: "cancel my meeting" (not read), "schedule a
  meeting with Bob" (not read), "what time is it" (get_time, not calendar)
- `handler.py`: Stage 2 handler that calls `get_todays_events()`,
  formats results as `[CALENDAR DATA]` block, injects into LLM context
  just like email does with `[EMAIL INBOX DATA]`

### 3. Wire into the proxy (`jane_web/jane_proxy.py`)

- Same pattern as email: when intent is `read_calendar`, fetch events
  server-side before sending to Opus/Sonnet, inject as context block
- Handle date parsing: "today", "tomorrow", "this week", "next Monday"

### 4. Standing brain instructions

- Add calendar reading protocol to the system prompt (similar to
  the Email Protocols section in CLAUDE.md standing brain rules)
- Jane should summarize events naturally: count them, mention times
  and titles, flag conflicts or back-to-back meetings

## Out of Scope (for now)

- Creating/editing/deleting calendar events (read-only first)
- Multiple calendar support (just primary calendar)
- Calendar notifications or proactive reminders

## Acceptance Criteria

1. User says "what's on my calendar today" → Jane reads back events
2. User says "any meetings tomorrow" → Jane reads tomorrow's events
3. If no events, Jane says so
4. If not signed in with Google, Jane tells user to sign in on web UI
5. Works from both Android and web clients

## References

- OAuth scopes: `vault_web/oauth.py:40`
- Token storage pattern: `agent_skills/email_oauth.py`
- Email handler reference: `jane_web/jane_v2/classes/read_email/`
- Intent classifier structure: `jane_web/jane_v2/classes/` (any existing class)
