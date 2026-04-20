---
Title: Clean up SMS/tool call display in chat bubbles
Priority: 2
Status: completed
Created: 2026-04-06
---

## Problem
When Jane drafts an SMS (e.g., "text [contact] I miss you"), the chat bubble shows raw tool call markup:
"To [contact]: I miss you already. [CLIENT_TOOL:contacts.sms_draft: {"query": "[contact]", "body": ...}]"

This is not user-friendly and breaks conversational flow, especially with TTS.

## Goal
Chat bubble should show something like:
"Here's the message to [contact]: *I miss you already.* Ready to send?"

The tool call still executes (the `client_tool_call` SSE event handles that), but the visible text should be clean and conversational.

## Approach
1. Update Jane's system prompt to format SMS drafts conversationally — tell the LLM to write the human-readable version and put the tool call on a separate line
2. In the Android delta handler, strip any remaining `[[CLIENT_TOOL:...]]` markup from the visible accumulated text (the server already extracts these into separate events, but edge cases may leak)
3. For TTS, use only the clean text (no tool markup spoken)

## Files
- `jane/context_builder.py` — system prompt update for SMS formatting
- `jane_web/jane_proxy.py` — verify tool call extraction is complete
- `android/.../ChatViewModel.kt` — strip leaked markup from display text
