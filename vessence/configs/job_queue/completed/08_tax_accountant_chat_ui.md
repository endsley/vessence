# Job: Replace Tax Accountant UI with Chat Interface

Status: complete
Completed: 2026-03-24 14:45 UTC
Notes: tax_accountant.html rewritten (628 lines). Chat interface with indigo theme, streaming SSE, file upload, model label, copy/audio buttons. Uses /api/jane/chat/stream with essence prefix. Separate session IDs. Welcome screen with quick-start buttons. Needs jane-web restart to serve.
Priority: 2
Model: opus
Created: 2026-03-24

## Objective
Replace the current mostly-empty tax accountant web page with a chat interface modeled after Jane's chat page. The user talks to the tax accountant essence through conversation — it asks questions, processes uploaded documents, and gives tax advice conversationally.

## Context
- Jane's chat UI is at `vault_web/templates/jane.html` — this is the reference implementation
- Tax accountant essence exists at `~/ambient/essences/tax_accountant_2025/`
- Current template `vault_web/templates/tax_accountant.html` is 578 lines but mostly empty/placeholder
- The essence has its own ChromaDB knowledge base (43 entries across 7 tax categories)
- Route exists: `GET /tax-accountant` in `jane_web/main.py`
- API routes exist for interview, calculate, forms, summary

## Design
The tax accountant chat should:
1. Look like Jane's chat page but with tax accountant branding (different accent color, tax icon, "Tax Accountant 2025" title)
2. Use the same streaming SSE pattern as Jane's chat
3. Route messages through the essence's brain (not Jane's brain) — use the essence's personality.md and ChromaDB knowledge
4. Support file uploads (W-2 PDFs, receipts, tax documents) via drag-and-drop or attach button
5. Show uploaded document status (parsed/processing/error)
6. Have a sidebar or header showing interview progress (which tax sections are complete)
7. Include Copy and Play audio buttons like Jane
8. Show model label on responses

## Steps
1. Create a new chat API endpoint for essence conversations: `POST /api/essence/{essence_id}/chat/stream`
   - This should be generic enough that ANY essence with `has_brain: true` can use it
   - Routes to the essence's own LLM brain with the essence's personality and ChromaDB context
2. Rewrite `tax_accountant.html` to be a chat interface based on `jane.html`
   - Strip out Jane-specific elements (prompt queue, announcements, live status)
   - Keep: chat bubbles, streaming, file upload, model label, copy/audio buttons
   - Add: tax-specific sidebar showing interview progress sections
   - Add: accent color override (indigo instead of violet)
3. Wire file uploads to the essence's document_parser.py
4. Test the full flow: open page → send greeting → upload a document → ask tax question
5. Run the essence post-build verification checklist from CLAUDE.md

## Verification
- `/tax-accountant` loads a chat interface (not empty page)
- Can send messages and receive streaming responses from the tax accountant brain
- File upload works (drag-and-drop and button)
- Responses reference tax knowledge from ChromaDB
- Model label shows on each response
- Copy and audio buttons work

## Files Involved
- `vault_web/templates/tax_accountant.html` — rewrite to chat UI
- `jane_web/main.py` — new generic essence chat stream endpoint
- `vault_web/templates/jane.html` — reference implementation
- `~/ambient/essences/tax_accountant_2025/personality.md` — brain personality
- `~/ambient/essences/tax_accountant_2025/functions/custom_tools.py` — tools the brain can call

## Notes
- The generic essence chat endpoint (`/api/essence/{id}/chat/stream`) will be reused by every future essence with `has_brain: true` — design it right the first time
- The tax accountant is the first essence with a chat UI, so this sets the pattern
- Keep the existing form-based API routes (interview/calculate/forms) — the chat brain can call them as tools
- Essence display order: Jane is #1, Work Log is last, others alphabetical
