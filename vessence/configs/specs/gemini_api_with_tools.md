# Spec: Gemini API Brain with Native Tool Execution

## Problem
The Gemini CLI cannot be driven programmatically for persistent streaming sessions. The PTY approach fails because Ink's TUI doesn't accept programmatic input. The per-turn `--resume` approach has 2-3s Node.js spawn overhead per message. Gemini must have full tool capabilities (file read/write, shell commands, code editing).

## Solution
Replace the Gemini CLI brain with a direct Gemini API integration using `google-generativeai` Python SDK. Define tools as Gemini function declarations. When Gemini requests a tool call, execute it in Python and return the result. Stream text deltas to the frontend in real time.

## Architecture

```
User message → jane_proxy.py → GeminiApiBrain
  → google.generativeai.ChatSession.send_message_async(stream=True)
  → Stream text deltas to frontend
  → If function_call in response:
      → Execute tool in Python (read_file, write_file, bash, etc.)
      → Send tool result back to Gemini
      → Continue streaming
  → Done
```

## Tool Definitions

Match the Claude CLI's tool set:

| Tool | Gemini Function Name | Parameters | Execution |
|---|---|---|---|
| Read file | `read_file` | `file_path`, `offset?`, `limit?` | `Path(file_path).read_text()` with offset/limit |
| Write file | `write_file` | `file_path`, `content` | `Path(file_path).write_text(content)` |
| Edit file | `edit_file` | `file_path`, `old_string`, `new_string` | String replace in file |
| Bash | `run_bash` | `command`, `timeout?` | `subprocess.run(command, shell=True)` |
| Grep | `grep_search` | `pattern`, `path?`, `glob?` | `subprocess.run(["rg", pattern, ...])` |
| Glob | `glob_files` | `pattern`, `path?` | `Path(path).glob(pattern)` |
| Web search | `web_search` | `query` | Google search API or fallback |

## Implementation

### New file: `jane/gemini_api_brain.py`

```python
class GeminiApiBrain:
    """Persistent Gemini brain using the API with function calling."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self.model = genai.GenerativeModel(
            model_name=model,
            tools=[TOOL_DEFINITIONS],
            system_instruction=None,  # set per-session
        )
        self.sessions: dict[str, ChatSession] = {}

    async def send_streaming(
        self, session_id, system_prompt, message, on_delta, on_status, on_tool_use
    ) -> str:
        session = self._get_or_create_session(session_id, system_prompt)
        response = await session.send_message_async(message, stream=True)

        full_text = ""
        async for chunk in response:
            if chunk.text:
                full_text += chunk.text
                on_delta(chunk.text)

            # Handle function calls
            for part in chunk.parts:
                if part.function_call:
                    on_status(f"Using tool: {part.function_call.name}")
                    result = await self._execute_tool(part.function_call)
                    on_tool_use(part.function_call.name, result)
                    # Send result back and continue
                    response = await session.send_message_async(
                        genai.protos.Content(parts=[
                            genai.protos.Part(function_response=result)
                        ]),
                        stream=True,
                    )
                    async for chunk2 in response:
                        if chunk2.text:
                            full_text += chunk2.text
                            on_delta(chunk2.text)

        return full_text
```

### Tool execution: `jane/tools/`

Each tool is a simple Python function:

```python
# jane/tools/file_tools.py
async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"Error: {file_path} does not exist"
    lines = path.read_text().splitlines()
    selected = lines[offset:offset+limit]
    return "\n".join(f"{i+offset+1}\t{line}" for i, line in enumerate(selected))

async def write_file(file_path: str, content: str) -> str:
    Path(file_path).write_text(content)
    return f"Written {len(content)} chars to {file_path}"

async def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    path = Path(file_path)
    text = path.read_text()
    if old_string not in text:
        return f"Error: old_string not found in {file_path}"
    text = text.replace(old_string, new_string, 1)
    path.write_text(text)
    return f"Edited {file_path}"

# jane/tools/shell_tools.py
async def run_bash(command: str, timeout: int = 120) -> str:
    result = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=timeout)
    return f"Exit code: {result.returncode}\n{stdout.decode()}\n{stderr.decode()}"
```

### Security
- Tools run with the same permissions as the Jane web process
- File operations are unrestricted (same as current CLI behavior)
- Shell commands run in the user's context
- The `JANE_WEB_PERMISSIONS` flag can gate tool approval (same as Claude's hook system)

### Session Management
- `ChatSession` objects are kept in memory (keyed by session_id)
- Conversation history is managed by the Gemini SDK (automatic context window)
- Sessions are pruned after idle timeout (same as current behavior)
- System prompt is injected on session creation

### Integration with jane_proxy.py
- `_use_persistent_gemini()` → replaced by `_use_gemini_api()`
- `_execute_brain_stream()` → calls `GeminiApiBrain.send_streaming()`
- Stream events (delta, status, tool_use, tool_result) map directly to existing frontend event types

## Auth
- Uses `GOOGLE_API_KEY` or `GEMINI_API_KEY` from environment or runtime .env
- Also supports OAuth credentials from `~/.gemini/oauth_creds.json` (convert to API client)
- No CLI needed for auth — API key is sufficient

## Benefits
- **~200ms to first token** (vs 2-3s CLI spawn)
- **True streaming** with function calling
- **Full tool capabilities** — same as CLI but executed in Python
- **Works in Docker** — no PTY, no Ink TUI, no trust prompts
- **Persistent sessions** — ChatSession stays in memory across turns
- **No Node.js dependency** for Gemini brain

## Files to Create/Modify
1. **NEW**: `jane/gemini_api_brain.py` — main brain class
2. **NEW**: `jane/tools/file_tools.py` — read, write, edit
3. **NEW**: `jane/tools/shell_tools.py` — bash, grep, glob
4. **NEW**: `jane/tools/__init__.py` — tool registry
5. **MODIFY**: `jane_web/jane_proxy.py` — wire up GeminiApiBrain
6. **MODIFY**: `jane/config.py` — Gemini API config constants
7. **KEEP**: `jane/persistent_gemini.py` — deprecated but kept for fallback

## Estimated Scope
- ~300 lines for gemini_api_brain.py
- ~150 lines for tool implementations
- ~50 lines proxy changes
- Testing: tool execution, streaming, multi-turn, error handling
