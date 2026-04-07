# Job #54: Conversational Acknowledgment System

Priority: 2
Status: completed
Created: 2026-03-29

## Description
Add [ACK] tags to Jane's system prompt so the brain outputs a brief contextual acknowledgment before the full response. Frontend parses the tags and displays/speaks the ack immediately.

### Spec
See `configs/specs/conversational_tts_ack.md`

### Key decisions (from discussion with the user):
1. Visual ack shown for ALL users (not TTS-only) — gives sense of response time
2. Personalized — brain uses user's name and references the actual topic
3. No separate LLM call — single prompt, brain outputs [ACK] first then [RESPONSE]
4. Ack should be cut short if real response arrives fast (greetings skip ack entirely)

### Changes:
- `jane/context_builder.py` — add ACK instruction to system prompt (~10 lines)
- `vault_web/templates/jane.html` — parse [ACK] tags in stream, display in status, TTS (~30 lines)
