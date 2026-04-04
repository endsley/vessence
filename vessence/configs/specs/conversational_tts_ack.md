# Spec: Conversational Acknowledgment System

## Problem
Jane feels unresponsive. The user sends a message and waits 5-40 seconds of silence before anything appears. Real conversations have immediate verbal cues ("sure, let me check", "hmm, good question"). This affects both TTS (phone) and visual (web) experiences.

## Solution
Prepend an ack instruction to the real prompt. The standing brain outputs an `[ACK]` line first (brief, contextual acknowledgment with time estimate), then the full `[RESPONSE]`. The frontend detects the `[ACK]` prefix, displays/speaks it immediately, then streams the response.

**Single prompt. Single brain turn. Zero extra LLM calls. Zero latency overhead.**

## How It Works

### System Prompt Addition
Add to Jane's system prompt (injected on turn 1):
```
RESPONSE FORMAT: Always begin your response with a brief acknowledgment line
wrapped in [ACK]...[/ACK] tags. This should be 1 short sentence that:
- Addresses the user by name
- Acknowledges what they asked
- Gives a sense of how long it will take
Then provide your full response after the tags.

Examples:
[ACK]Sure Chieh, let me check the weather real quick.[/ACK]
The weather in Boston today is...

[ACK]On it, Chieh — let me dig into that Docker auth issue.[/ACK]
The root cause is...

[ACK]Good question Chieh. This is going to take some research, I'll work through it.[/ACK]
After analyzing the codebase...

For simple greetings, skip the [ACK] tags and just respond naturally.
```

### Frontend Processing (jane.html)
When streaming deltas, the frontend watches for the `[ACK]...[/ACK]` pattern:

```javascript
// In consumeStream / applyStreamEvent
if (event.type === 'delta') {
    accumulatedText += event.data;

    // Check for ACK block
    const ackMatch = accumulatedText.match(/\[ACK\](.*?)\[\/ACK\]/);
    if (ackMatch && !ackDelivered) {
        const ackText = ackMatch[1].trim();
        // Display ack in status area
        msg.status = ackText;
        // Speak ack immediately if TTS is on
        if (ttsEnabled) speakText(ackText);
        ackDelivered = true;
        // Strip ACK from the displayed text
        accumulatedText = accumulatedText.replace(/\[ACK\].*?\[\/ACK\]\s*/, '');
    }

    // Display remaining text as normal response
    msg.text = accumulatedText;
}
```

### Why This Works
- The standing brain has **full conversation context** — it knows "fix that bug" means the Docker auth bug from 2 turns ago
- The ack is the **first few tokens** generated — arrives in ~1-2s (time to first token + a few words)
- The brain continues generating the real response immediately after — no pause, no second call
- **Personalized**: brain uses the user's name and references the actual topic
- **Contextual time estimate**: brain knows if this needs a quick lookup or deep research

### Visual Behavior (TTS off)
- Ack text appears in the **status area** (above the response bubble), not as a separate message
- Status shows: "Sure Chieh, let me look into that Docker issue..."
- Response text streams below as normal
- When response completes, status clears

### TTS Behavior (TTS on)
- Ack text is spoken immediately via browser TTS
- While ack is speaking, response continues streaming (text appears)
- When ack finishes speaking, the full response is spoken
- If response is very short (greetings), skip ack — just speak the response directly

### Greeting Fast-Path
For simple greetings ("hey Jane", "how are you?"), the brain skips the `[ACK]` tags entirely and responds directly. The system prompt says "For simple greetings, skip the [ACK] tags."

## Files to Modify
1. `jane/context_builder.py` — add ACK instruction to system prompt
2. `vault_web/templates/jane.html` — parse [ACK] tags in stream consumer, display in status, speak via TTS
3. No backend changes needed — the ack is just text from the brain, parsed by the frontend

## Benefits
- Zero infrastructure changes (no new LLM calls, no classifier changes)
- Works with any brain provider (Claude, Gemini, OpenAI)
- Personalized and contextual (brain has full history)
- Ack arrives in ~1-2s (time to generate first sentence)
- Both visual and audible feedback
- Graceful degradation: if brain doesn't output [ACK] tags, everything still works

## Estimated Scope
- ~10 lines in context_builder.py (system prompt addition)
- ~30 lines in jane.html (ACK parsing + TTS)
- Testing: verify ACK appears, TTS speaks it, response streams normally
