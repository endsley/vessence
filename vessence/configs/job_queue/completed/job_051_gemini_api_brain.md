# Job #51: Gemini API Brain with Native JS Tool Execution

Priority: 2
Status: completed
Created: 2026-03-29

## Description
Replace the broken Gemini CLI PTY-based brain with a Gemini API + Node.js tool bridge architecture.

### Architecture
1. **Python**: `jane/gemini_api_brain.py` — manages Gemini API streaming via `google-generativeai` SDK
2. **Node.js**: `jane/tools/gemini_tool_bridge.js` — imports and executes tools from `@google/gemini-cli-core` 
3. **Interface**: Python calls Node.js bridge when Gemini API returns a function_call, sends result back to API

### Components to Build
- `jane/gemini_api_brain.py` — Gemini API streaming with function calling, session management
- `jane/tools/gemini_tool_bridge.js` — Node.js bridge that imports gemini-cli-core tool executors
- Modify `jane_proxy.py` to use GeminiApiBrain instead of persistent_gemini
- Tool definitions matching gemini-cli-core's 20+ built-in tools
- Stream events (delta, tool_use, tool_result, status) matching existing frontend protocol

### Key Benefits
- ~200ms to first token (vs 2-3s CLI spawn)
- True streaming with function calling
- Full tool capabilities (all gemini-cli-core tools, natively in JS)
- Works in Docker without PTY/Ink issues
- Persistent sessions via in-memory ChatSession

### Spec
See `configs/specs/gemini_api_with_tools.md` (needs updating for the Node.js bridge approach)

### Dependencies
- `google-generativeai` Python SDK (already in requirements)
- `@google/gemini-cli-core` npm package (already installed with gemini-cli)
- Node.js (already installed in Docker image)

## Result
Job 051 is done. Here's what was already in place and what I fixed:  **Already implemented (before this session):** - `jane/gemini_api_brain.py` — full brain class with streaming + automatic function calling - `jane/tools/gemini_tool_bridge.js` — Node.js HTTP tool server with 8 tools - `jane_proxy.p
