# Job: TTS Voice-Aware Responses — Spoken Summary Block

Status: complete
Completed: 2026-03-24 00:30 UTC
Notes: 7 files modified. context_builder injects spoken block instruction when tts_enabled. Web + Android extract <spoken> block for TTS, strip from display. Fallback: speak first 2 sentences if no block. tts_enabled flag passed from client through proxy to context builder.
Priority: 2
Model: sonnet
Created: 2026-03-23

## Objective
When TTS is enabled, Jane writes the full detailed response as normal, plus appends a short conversational `<spoken>` block. The UI displays the full text but TTS only reads the spoken block.

## Design

### System Prompt Injection
When the request comes from a TTS-enabled client (web with TTS on, Android with voice active), add to Jane's system prompt:
```
After your full response, add a <spoken> block with a 2-4 sentence conversational summary meant to be read aloud. No markdown, no tables, no code blocks, no bullet points. Speak naturally as if answering a question face-to-face.
```

### Response Parsing
- Server extracts `<spoken>...</spoken>` from Jane's response
- Full response (minus the spoken tag) → displayed in chat bubble
- Spoken text → sent to TTS engine
- If no `<spoken>` block present, fall back to current behavior (TTS reads the full response)

### Client Integration
- **Web (jane.html):** When TTS is active, parse the response for `<spoken>` before sending to SpeechSynthesis
- **Android (ChatViewModel.kt):** Same — extract spoken block before passing to AndroidTtsManager
- **CLI:** No change needed (CLI doesn't use TTS)

### Platform Detection
- Web: `ttsEnabled` flag already exists in the Alpine.js state
- Android: `ttsEnabled` flag in ChatViewModel
- Pass a `tts_enabled=true` param in the chat request so the server knows to inject the prompt hint

## Files Involved
- `jane/context_builder.py` — inject spoken-summary instruction when tts_enabled
- `jane_web/main.py` or `jane_web/jane_proxy.py` — pass tts_enabled from request to context builder
- `vault_web/templates/jane.html` — parse `<spoken>` block, send only that to TTS
- `android/.../ui/chat/ChatViewModel.kt` — parse `<spoken>` block for TTS
- `android/.../data/repository/ChatRepository.kt` — pass tts_enabled in request

## Notes
- The `<spoken>` block should be stripped from the displayed message — user sees clean text
- If the LLM forgets to add `<spoken>`, graceful fallback: TTS reads first 2 sentences of the full response
- Keep spoken summaries conversational — no "Here's a summary:" preamble
