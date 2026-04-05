# Job #8: Parallel Gemma4/Claude Routing with Ack Forwarding

Priority: 2
Status: pending
Created: 2026-04-04

## Description
Currently gemma4 runs sequentially before Claude, adding 0.8-1.3s latency on every delegate request. Change to parallel execution and forward gemma4's ack into Claude's context.

### Current flow (sequential):
1. Gemma4 classifies (0.8-1.3s)
2. If delegate: emit ack, then start Claude
3. Claude runs (5-20s)
4. Total: 6-21s

### Target flow (parallel):
1. Start gemma4 AND Claude simultaneously
2. Gemma4 finishes first (~0.8s) → emit contextual ack, speak via TTS
3. Inject gemma4's ack into Claude's context as an assistant turn
4. Claude continues with awareness of what gemma4 already told the user
5. If gemma4 self-handles: cancel Claude, use gemma4's response
6. Total: 5-20s (saves 0.8-1.3s on delegate path)

### Context forwarding:
- Gemma4's ack becomes part of the conversation: `{"role": "assistant", "content": "[ACK] Looking into the wake word issue."}`
- Claude sees this and can follow up: status updates that build on the ack
- Claude should NOT repeat the ack — it knows gemma4 already said it

### Implementation:
1. `jane_proxy.py`: Launch gemma4 and Claude as parallel asyncio tasks
2. Gemma4 task: classify + generate ack → emit immediately
3. Claude task: wait for gemma4 result → inject ack into context → generate response
4. If gemma4 self-handles: cancel Claude task, emit gemma4 response as done

### Risk:
- If gemma4 times out, Claude should still work (already in progress)
- Cancel logic must be clean — no orphaned Claude processes
