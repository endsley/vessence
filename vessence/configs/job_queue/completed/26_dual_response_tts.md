# Job: Dual Response — Short Spoken + Full Detail with Disclosure Triangle

Status: completed
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
When TTS mode is on, ask the LLM to return two versions of the response: a short spoken summary and the full detailed answer. The chat bubble shows the short version (and reads it aloud), with a closed disclosure triangle below that reveals the full version when opened.

## UX Flow
1. User sends message (TTS mode on)
2. Jane responds with a bubble showing:
   ```
   [Short spoken answer — 1-3 sentences, plain English, no symbols]

   ▸ Show full response
   ```
3. TTS reads the short answer aloud
4. User clicks "▸ Show full response" → expands to reveal the detailed answer (markdown, code, tables, etc.)
5. If TTS is off, just show the full response as usual (no dual mode)

## Implementation

### Backend (context_builder.py)
Update `TTS_SPOKEN_BLOCK_INSTRUCTION` to ask for both versions:
```
When TTS mode is ON, structure your response as:
<spoken>1-3 sentence summary in plain spoken English. No symbols, no markdown.</spoken>

Then provide the full detailed response below (with markdown, code, tables as needed).
```

The `<spoken>` tag is already partially supported — jane.html already strips `<spoken>` blocks from display and extracts them for TTS. We just need to flip the logic: display the spoken text as the primary bubble, and the rest as the expandable detail.

### Backend (jane_proxy.py)
No changes needed — the response text comes through as-is with `<spoken>` tags.

### Frontend (jane.html)
1. When `msg.text` contains `<spoken>...</spoken>`:
   - Extract the spoken text → show as the main bubble content
   - Extract everything outside `<spoken>` → store as `msg.fullResponse`
   - TTS reads `msg.spokenText`
2. If `msg.fullResponse` exists, render a disclosure triangle below:
   ```html
   <details>
     <summary class="text-xs text-slate-500 cursor-pointer">▸ Show full response</summary>
     <div x-html="formatMessage(msg.fullResponse)" class="mt-2"></div>
   </details>
   ```
3. When TTS is off, show full response directly (no split)

### Display rules
- Short spoken text: normal size, white, plain text (no markdown rendering)
- Full response: collapsible, rendered with formatMessage() (markdown, code, LaTeX)
- Disclosure triangle: closed by default, small grey text
- If response has no `<spoken>` tag, display everything as usual (backward compatible)

## Verification
- TTS on: bubble shows short summary, reads it aloud, triangle reveals full detail
- TTS off: bubble shows full response as normal
- Code/tables/markdown only appear in the expanded section, not the spoken part
- No parentheses, brackets, or symbols in the spoken text
- Disclosure triangle works (open/close)
- Backward compatible: old responses without `<spoken>` tags display normally

## Files Involved
- `jane/context_builder.py` — update TTS_SPOKEN_BLOCK_INSTRUCTION
- `vault_web/templates/jane.html` — split display logic, disclosure triangle
