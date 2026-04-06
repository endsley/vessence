"""
gemini_api_brain.py — Gemini brain using the Google GenAI API with streaming
and function calling via a Node.js tool bridge.

Replaces the broken persistent_gemini PTY approach. Uses google.genai SDK
for streaming text + function calling. Tool calls are executed via the
tool bridge HTTP server (jane/tools/gemini_tool_bridge.js).
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator, Callable

import httpx

logger = logging.getLogger("jane.gemini_api_brain")

# Tool bridge configuration
TOOL_BRIDGE_PORT = int(os.environ.get("TOOL_BRIDGE_PORT", "7799"))
TOOL_BRIDGE_URL = f"http://127.0.0.1:{TOOL_BRIDGE_PORT}"

# Tool definitions for the Gemini API (function declarations)
TOOL_DECLARATIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file with optional line range.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "start_line": {"type": "integer", "description": "Start line (1-based, optional)"},
                "end_line": {"type": "integer", "description": "End line (optional)"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "edit",
        "description": "Edit a file by replacing old_string with new_string.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "old_string": {"type": "string", "description": "Exact text to find and replace"},
                "new_string": {"type": "string", "description": "Replacement text"},
                "allow_multiple": {"type": "boolean", "description": "Replace all occurrences"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "shell",
        "description": "Run a shell command and return stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)"},
                "is_background": {"type": "boolean", "description": "Run in background"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "grep",
        "description": "Search file contents using regex pattern.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search"},
                "dir_path": {"type": "string", "description": "Directory to search in"},
                "include_pattern": {"type": "string", "description": "File glob to include"},
                "names_only": {"type": "boolean", "description": "Only show file names"},
                "case_sensitive": {"type": "boolean", "description": "Case sensitive search"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. *.py)"},
                "dir_path": {"type": "string", "description": "Directory to search in"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "ls",
        "description": "List directory contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "Directory path"},
            },
            "required": ["dir_path"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
]


class GeminiApiBrain:
    """Persistent Gemini brain using the Google GenAI API with tool execution."""

    def __init__(self):
        self._sessions: dict[str, object] = {}  # session_id → ChatSession
        self._client = None
        self._bridge_process: subprocess.Popen | None = None
        self._bridge_healthy = False

    def _ensure_client(self):
        """Lazily initialize the Gemini client."""
        if self._client is not None:
            return
        from google import genai
        # Load API key from runtime .env if not in environment
        from llm_brain.v1.brain_adapters import _load_runtime_env_keys
        _load_runtime_env_keys(("GOOGLE_API_KEY", "GEMINI_API_KEY"))
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("No Gemini API key found (GEMINI_API_KEY or GOOGLE_API_KEY)")
        self._client = genai.Client(api_key=api_key)
        logger.info("Gemini API client initialized")

    async def _ensure_bridge(self):
        """Start the tool bridge if not running."""
        if self._bridge_healthy:
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"{TOOL_BRIDGE_URL}/health", timeout=2)
                    if r.status_code == 200:
                        return
            except Exception:
                self._bridge_healthy = False

        # Start the bridge
        bridge_script = Path(__file__).parent / "tools" / "gemini_tool_bridge.js"
        if not bridge_script.exists():
            logger.warning("Tool bridge script not found: %s", bridge_script)
            return

        if self._bridge_process and self._bridge_process.poll() is None:
            self._bridge_process.kill()
            self._bridge_process.wait()

        self._bridge_process = subprocess.Popen(
            ["node", str(bridge_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "TOOL_BRIDGE_PORT": str(TOOL_BRIDGE_PORT)},
        )
        # Wait for it to be ready
        for _ in range(20):
            await asyncio.sleep(0.25)
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"{TOOL_BRIDGE_URL}/health", timeout=2)
                    if r.status_code == 200:
                        self._bridge_healthy = True
                        logger.info("Tool bridge started (pid=%d, port=%d)", self._bridge_process.pid, TOOL_BRIDGE_PORT)
                        return
            except Exception:
                continue
        logger.error("Tool bridge failed to start within 5s")

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool via the HTTP bridge."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{TOOL_BRIDGE_URL}/execute",
                    json={"tool": tool_name, "args": tool_args},
                    timeout=130,  # shell commands can take up to 120s
                )
                data = resp.json()
                return data.get("result", data.get("error", "Unknown error"))
        except Exception as exc:
            return f"Tool execution failed: {exc}"

    async def send_streaming(
        self,
        session_id: str,
        system_prompt: str,
        message: str,
        on_delta: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_tool_use: Callable[[str, str], None] | None = None,
        model: str = "gemini-2.5-pro",
        timeout_seconds: float = 300,
    ) -> str:
        """Send a message and stream the response with tool execution.

        Returns the full response text.
        """
        self._ensure_client()
        await self._ensure_bridge()

        from google.genai import types

        # Define Python callable tools for automatic function calling
        # These must be SYNCHRONOUS — the SDK calls them from a sync context.
        import requests as _req

        def _call_bridge(tool_name: str, args: dict) -> str:
            """Synchronous call to the tool bridge."""
            try:
                r = _req.post(f"{TOOL_BRIDGE_URL}/execute",
                              json={"tool": tool_name, "args": args}, timeout=130)
                data = r.json()
                return data.get("result", data.get("error", "Unknown error"))
            except Exception as e:
                return f"Tool error: {e}"

        def read_file(file_path: str, start_line: int = 0, end_line: int = 0) -> str:
            """Read the contents of a file with optional line range."""
            return _call_bridge("read_file", {"file_path": file_path, "start_line": start_line or None, "end_line": end_line or None})

        def write_file(file_path: str, content: str) -> str:
            """Create or overwrite a file with the given content."""
            return _call_bridge("write_file", {"file_path": file_path, "content": content})

        def edit(file_path: str, old_string: str, new_string: str) -> str:
            """Edit a file by replacing old_string with new_string."""
            return _call_bridge("edit", {"file_path": file_path, "old_string": old_string, "new_string": new_string})

        def shell(command: str, timeout: int = 120) -> str:
            """Run a shell command and return stdout/stderr."""
            return _call_bridge("shell", {"command": command, "timeout": timeout})

        def grep(pattern: str, dir_path: str = "") -> str:
            """Search file contents using regex pattern."""
            return _call_bridge("grep", {"pattern": pattern, "dir_path": dir_path})

        def list_directory(dir_path: str) -> str:
            """List directory contents."""
            return _call_bridge("ls", {"dir_path": dir_path})

        def web_search(query: str) -> str:
            """Search the web for information. Returns formatted search results."""
            try:
                from agent_skills.web_search_utils import web_search as _ws
                return _ws(query) or "No results found."
            except Exception as e:
                return f"Web search error: {e}"

        callable_tools = [read_file, write_file, edit, shell, grep, list_directory, web_search]

        # Get or create chat session
        if session_id not in self._sessions:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt or None,
                tools=callable_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False,
                    maximum_remote_calls=10,
                ),
                temperature=0.7,
            )
            self._sessions[session_id] = self._client.chats.create(
                model=model,
                config=config,
            )
            logger.info("[%s] Created new Gemini chat session (model=%s)", session_id[:12], model)

        chat = self._sessions[session_id]
        full_text = ""

        try:
            # Send message with streaming — automatic function calling handles tool execution
            response = chat.send_message_stream(message)

            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    if on_delta:
                        on_delta(chunk.text)

        except Exception as exc:
            logger.error("[%s] Gemini API error: %s", session_id[:12], exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc

        return full_text

    def remove_session(self, session_id: str):
        """Remove a chat session."""
        self._sessions.pop(session_id, None)

    async def shutdown(self):
        """Clean up resources."""
        if self._bridge_process and self._bridge_process.poll() is None:
            self._bridge_process.kill()
            self._bridge_process.wait()
        self._sessions.clear()


# Singleton
_gemini_api_brain: GeminiApiBrain | None = None


def get_gemini_api_brain() -> GeminiApiBrain:
    global _gemini_api_brain
    if _gemini_api_brain is None:
        _gemini_api_brain = GeminiApiBrain()
    return _gemini_api_brain
