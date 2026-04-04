# Job: Tax Accountant as Jane Essence Mode (Replaces Separate UI)

Status: done
Priority: 2
Model: opus
Created: 2026-03-24

## Objective
Replace the standalone tax accountant chat page with an essence-loading pattern: clicking Tax Accountant on the essences page redirects to Jane's chat, where Jane is initialized with the tax accountant's instructions, tools, and ChromaDB. No separate UI — Jane IS the tax accountant when the essence is active.

## Context
Architecture decision (2026-03-24): Essences do not get their own chat UIs. Every essence activates through Jane's existing chat interface. Loading an essence means:
1. Jane receives the essence's personality/instructions as an overlay
2. The essence's ChromaDB collection is added to Jane's retrieval pipeline
3. Jane gets access to the essence's tools (custom_tools.py functions)
4. Jane opens with a warm kickoff message specific to the essence

This supersedes job 08 (separate tax accountant chat UI). The tax_accountant.html page is no longer needed as a standalone chat — it should redirect to Jane with the essence activated.

## Pre-conditions
- Tax accountant essence exists at `~/ambient/essences/tax_accountant_2025/` with ChromaDB, personality.md, and tools
- Jane's chat works on web (`/jane` route)
- Essence loading/unloading API exists (`/api/essences/active`)

## Steps
1. **Essence activation flow**: When user clicks Tax Accountant on essences page → call API to set it as active essence → redirect to Jane's chat (`/jane`)
2. **Jane init with essence**: When Jane's chat loads and an essence is active:
   - Load the essence's `personality.md` as additional system instructions
   - Add the essence's ChromaDB collection to the retrieval pipeline (queried alongside Jane's universal memory)
   - Register the essence's tools (interview_step, upload_document, calculate_tax, generate_forms, etc.)
   - Jane sends a kickoff message: "Hey, I now have all the knowledge of a tax accountant. Let's get your taxes done — I'll ask you a series of questions and collect documents from you, and little by little we'll get everything filed. Ready to start?"
3. **Essence persistence**: The essence stays active until explicitly unloaded. Navigating away from Jane's chat and back should preserve the active essence state.
4. **Essence deactivation**: When user unloads the essence (from essences page or a command), Jane drops the extra instructions, tools, and ChromaDB — back to baseline Jane.
5. **Tax accountant route redirect**: Change `/tax-accountant` to redirect to `/jane` with essence activation (or remove it and handle entirely through the essences page).
6. **Generic pattern**: This must work for ANY essence, not just the tax accountant. The activation flow should read the essence's manifest.json to determine what to load.

## Verification
- Clicking Tax Accountant on essences page → lands on Jane's chat with tax kickoff message
- Jane can answer tax questions using the tax ChromaDB knowledge
- Jane can call tax tools (interview_step, upload_document, calculate_tax, generate_forms)
- File upload in Jane's chat works with the tax document parser
- Unloading the essence → Jane returns to normal, no tax context in responses
- Loading a different essence → switches cleanly
- Navigating away and back to Jane → essence still active

## Files Involved
- `jane_web/main.py` — essence activation logic, modify Jane's chat endpoint
- `jane_web/jane_proxy.py` — inject essence instructions + ChromaDB into Jane's brain
- `vault_web/templates/jane.html` — show active essence indicator, kickoff message
- `vault_web/static/essences.html` — change "open" button to activate + redirect to Jane
- `~/ambient/essences/tax_accountant_2025/personality.md` — instructions Jane absorbs
- `~/ambient/essences/tax_accountant_2025/manifest.json` — capabilities, tools, ChromaDB path

## Notes
- This is the pattern for ALL essences going forward — tax accountant is just the first
- Job 08 (separate tax chat UI) is superseded by this approach
- The essence's conversation data gets written to the essence's ChromaDB, so when unloaded, that context is preserved for next time
- Jane's universal memory is always available regardless of which essence is active
- The kickoff message should feel like Jane, not a generic bot — she's telling you she loaded new expertise, not becoming a different person
