"""Persistent Claude CLI sessions via --resume.

Instead of spawning a new `claude -p` process per message (re-sending the
entire system prompt + history each time), we:
  1. First message: `claude --print --output-format stream-json -p "prompt"`
     → capture session_id from the JSON result
  2. Subsequent messages: `claude --print --output-format stream-json --resume <session_id> -p "message"`
     → Claude maintains its own context window internally

This dramatically reduces token usage and latency for multi-turn conversations.

Context Window Monitor:
  Tracks estimated token usage per session. When usage approaches the model's
  context limit (~70%), automatically rotates to a fresh session with a
  conversation summary carried over via ChromaDB.
"""
import asyncio
import json
import logging
import os
import signal
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("jane.persistent_claude")

# Context window limits by model family (input tokens).
# Conservative estimates — rotate well before hitting the wall.
_MODEL_CONTEXT_LIMITS = {
    "claude-opus-4":    200_000,
    "claude-sonnet-4":  200_000,
    "claude-haiku-4":   200_000,
    "default":          200_000,
}

# Rotate when estimated usage exceeds this fraction of the context window
_ROTATION_THRESHOLD = 0.70


def _get_context_limit(model: str | None) -> int:
    """Get the context window size for a model, with fallback."""
    if not model:
        return _MODEL_CONTEXT_LIMITS["default"]
    for prefix, limit in _MODEL_CONTEXT_LIMITS.items():
        if prefix != "default" and model.startswith(prefix):
            return limit
    return _MODEL_CONTEXT_LIMITS["default"]


@dataclass
class ClaudePersistentSession:
    session_id: str  # Our session ID (from web/android)
    claude_session_id: str | None = None  # Claude CLI's session ID
    last_used: float = field(default_factory=time.time)
    turn_count: int = 0
    # Token tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    prompt_chars_sent: int = 0
    response_chars_received: int = 0
    model: str | None = None

    def is_fresh(self) -> bool:
        return self.claude_session_id is None

    @property
    def estimated_tokens(self) -> int:
        """Best estimate of total tokens consumed in this session."""
        # Prefer actual token counts from the result event if available
        if self.total_input_tokens > 0:
            return self.total_input_tokens + self.total_output_tokens
        # Fallback: rough char-based estimate (÷4 ≈ tokens)
        return (self.prompt_chars_sent + self.response_chars_received) // 4

    def should_rotate(self) -> bool:
        """Check if this session should be rotated to a fresh one."""
        if self.is_fresh():
            return False
        limit = _get_context_limit(self.model)
        threshold = int(limit * _ROTATION_THRESHOLD)
        return self.estimated_tokens >= threshold


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess and its entire process group (children, grandchildren, etc.).

    Claude CLI spawns Bun workers, tokio runtimes, JIT workers, etc. as child
    processes. A plain proc.kill() only kills the parent — the children become
    orphans that block systemd shutdown for 2+ minutes.
    """
    if proc.returncode is not None:
        return
    pid = proc.pid
    try:
        # Kill the entire process group rooted at this PID
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        # Process already dead or we don't own it — fall back to direct kill
        try:
            proc.kill()
        except ProcessLookupError:
            pass


class ClaudePersistentManager:
    """Manages persistent Claude CLI sessions, one per web/android session."""

    # Stale session threshold: kill sessions unused for 30 minutes
    _STALE_SESSION_SECS = 1800
    _MAX_SESSIONS = 20  # hard cap on concurrent sessions

    def __init__(self):
        self._sessions: dict[str, ClaudePersistentSession] = {}
        self._lock = asyncio.Lock()
        self._claude_bin = os.environ.get("CLAUDE_BIN", shutil.which("claude") or "claude")
        self._active_procs: dict[str, asyncio.subprocess.Process] = {}  # track running subprocesses

    async def get(self, session_id: str) -> "ClaudePersistentSession":
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                # Evict oldest session if at capacity
                if len(self._sessions) >= self._MAX_SESSIONS:
                    oldest_id = min(self._sessions, key=lambda sid: self._sessions[sid].last_used)
                    old = self._sessions.pop(oldest_id, None)
                    proc = self._active_procs.pop(oldest_id, None)
                    if proc and proc.returncode is None:
                        _kill_process_tree(proc)
                    logger.info("[%s] Evicted oldest session to stay under %d cap", oldest_id[:12], self._MAX_SESSIONS)
                session = ClaudePersistentSession(session_id=session_id)
                self._sessions[session_id] = session
            session.last_used = time.time()
            return session

    async def end(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            proc = self._active_procs.pop(session_id, None)
            if proc and proc.returncode is None:
                _kill_process_tree(proc)

    def force_shutdown_all(self) -> int:
        """Kill ALL active subprocesses immediately. No lock, no await.

        Called during server shutdown to avoid deadlocking on self._lock
        (which may be held by an in-progress turn). This is intentionally
        synchronous and brute-force — the server is going down anyway.
        """
        killed = 0
        for sid, proc in list(self._active_procs.items()):
            _kill_process_tree(proc)
            killed += 1
        self._active_procs.clear()
        self._sessions.clear()
        logger.info("Force-shutdown: killed %d Claude CLI processes", killed)
        return killed

    async def reap_stale_sessions(self) -> int:
        """Kill sessions unused for >30 minutes. Returns count of reaped sessions."""
        now = time.time()
        reaped = 0
        async with self._lock:
            stale_ids = [
                sid for sid, sess in self._sessions.items()
                if now - sess.last_used > self._STALE_SESSION_SECS
            ]
            for sid in stale_ids:
                self._sessions.pop(sid, None)
                proc = self._active_procs.pop(sid, None)
                if proc and proc.returncode is None:
                    _kill_process_tree(proc)
                reaped += 1
        if reaped:
            logger.info(f"Reaped {reaped} stale Claude sessions (>{self._STALE_SESSION_SECS}s idle)")
        return reaped

    async def run_turn(
        self,
        session_id: str,
        prompt_text: str,
        on_delta: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        timeout_seconds: float = 300.0,
        model: str | None = None,
        yolo: bool = False,
    ) -> str:
        """Execute a turn in a persistent Claude session.

        First call creates a new session, subsequent calls resume it.
        Streams deltas via on_delta callback.
        Automatically rotates the session if the context window is filling up.
        Returns the full response text.
        """
        session = await self.get(session_id)

        # Store model for context limit lookups
        if model and not session.model:
            session.model = model

        # Check if we need to rotate before this turn
        if session.should_rotate():
            await self._rotate_session(session, on_status)

        # Track prompt size
        session.prompt_chars_sent += len(prompt_text)

        cmd = [self._claude_bin, "--print", "--verbose", "--output-format", "stream-json"]

        if model:
            cmd.extend(["--model", model])
        if yolo:
            cmd.append("--dangerously-skip-permissions")

        # Resume existing session or start fresh
        if session.claude_session_id:
            cmd.extend(["--resume", session.claude_session_id])

        cmd.extend(["-p", prompt_text])

        logger.info(
            "[%s] Running turn %d (claude_session=%s, prompt_len=%d, est_tokens=%d)",
            session_id[:12],
            session.turn_count + 1,
            session.claude_session_id or "new",
            len(prompt_text),
            session.estimated_tokens,
        )

        try:
            response_text, new_claude_session_id, usage = await self._execute_streaming(
                cmd, on_delta, on_status, timeout_seconds, session_id=session_id
            )
        except Exception as exc:
            logger.error("[%s] Turn failed: %s", session_id[:12], exc)
            # If resume failed, try fresh (session may have expired)
            if session.claude_session_id:
                logger.info("[%s] Retrying as fresh session", session_id[:12])
                session.claude_session_id = None
                session.total_input_tokens = 0
                session.total_output_tokens = 0
                session.prompt_chars_sent = len(prompt_text)
                session.response_chars_received = 0
                cmd_fresh = [self._claude_bin, "--print", "--verbose", "--output-format", "stream-json"]
                if model:
                    cmd_fresh.extend(["--model", model])
                if yolo:
                    cmd_fresh.append("--dangerously-skip-permissions")
                cmd_fresh.extend(["-p", prompt_text])
                response_text, new_claude_session_id, usage = await self._execute_streaming(
                    cmd_fresh, on_delta, on_status, timeout_seconds, session_id=session_id
                )
            else:
                raise

        # Update session state
        if new_claude_session_id:
            session.claude_session_id = new_claude_session_id
        session.turn_count += 1
        session.last_used = time.time()
        session.response_chars_received += len(response_text)

        # Update token tracking from usage data if available
        if usage:
            session.total_input_tokens = usage.get("input_tokens", session.total_input_tokens)
            session.total_output_tokens = usage.get("output_tokens", session.total_output_tokens)
            if usage.get("model"):
                session.model = usage["model"]

        logger.info(
            "[%s] Turn %d complete (claude_session=%s, response_len=%d, est_tokens=%d/%d [%.0f%%])",
            session_id[:12],
            session.turn_count,
            session.claude_session_id or "unknown",
            len(response_text),
            session.estimated_tokens,
            _get_context_limit(session.model),
            (session.estimated_tokens / _get_context_limit(session.model)) * 100,
        )

        return response_text

    async def _rotate_session(
        self,
        session: ClaudePersistentSession,
        on_status: Callable[[str], None] | None,
    ) -> None:
        """Rotate to a fresh Claude session, preserving context via ChromaDB."""
        logger.info(
            "[%s] Rotating session (est_tokens=%d, turns=%d)",
            session.session_id[:12],
            session.estimated_tokens,
            session.turn_count,
        )

        if on_status:
            on_status("Refreshing session context...")

        # Generate a conversation summary using Claude CLI
        summary = await self._generate_session_summary(session)

        # Save summary to ChromaDB for retrieval by context_builder
        if summary:
            try:
                vessence_home = os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))
                add_fact_script = os.path.join(vessence_home, "agent_skills", "add_fact.py")
                python_bin = os.environ.get("VENV_BIN", shutil.which("python3") or "python3")
                if os.path.exists(os.path.join(os.path.dirname(python_bin or ""), "python")):
                    python_bin = os.path.join(os.path.dirname(python_bin), "python")

                # Use the venv python if available
                venv_python = os.environ.get("ADK_VENV_PYTHON", "")
                if venv_python and os.path.exists(venv_python):
                    python_bin = venv_python

                proc = await asyncio.create_subprocess_exec(
                    python_bin, add_fact_script,
                    f"Session handoff ({session.session_id[:12]}): {summary}",
                    "--topic", "session_handoff",
                    "--subtopic", session.session_id[:12],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    await asyncio.wait_for(proc.wait(), timeout=30)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    logger.warning("[%s] Session summary save timed out", session.session_id[:12])
                else:
                    logger.info("[%s] Session summary saved to ChromaDB", session.session_id[:12])
            except Exception as e:
                logger.warning("[%s] Failed to save session summary: %s", session.session_id[:12], e)

        # Reset session state — next turn will create a fresh CLI session
        old_turns = session.turn_count
        old_tokens = session.estimated_tokens
        session.claude_session_id = None
        session.turn_count = 0
        session.total_input_tokens = 0
        session.total_output_tokens = 0
        session.prompt_chars_sent = 0
        session.response_chars_received = 0

        if on_status:
            on_status("")

        logger.info(
            "[%s] Session rotated (was %d turns, ~%d tokens). Fresh session will start on next turn.",
            session.session_id[:12],
            old_turns,
            old_tokens,
        )

    async def _generate_session_summary(self, session: ClaudePersistentSession) -> str:
        """Ask the current Claude session to summarize itself before we discard it."""
        if not session.claude_session_id:
            return ""

        summary_prompt = (
            "SYSTEM: This conversation session is about to be refreshed due to context limits. "
            "Please provide a concise summary (max 200 words) of: "
            "1) What topics we discussed, "
            "2) Any decisions that were made, "
            "3) Any pending tasks or follow-ups. "
            "Be specific — this summary will be used to restore context in the new session."
        )

        cmd = [
            self._claude_bin, "--print", "--output-format", "text",
            "--max-tokens", "500",
            "--resume", session.claude_session_id,
            "-p", summary_prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/tmp",
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            summary = stdout.decode(errors="ignore").strip()
            logger.info("[%s] Generated session summary (%d chars)", session.session_id[:12], len(summary))
            return summary
        except Exception as e:
            logger.warning("[%s] Failed to generate session summary: %s", session.session_id[:12], e)
            return ""

    # Human-readable labels for Claude Code tools
    _TOOL_LABELS = {
        "Read": "Reading file",
        "Edit": "Editing file",
        "Write": "Writing file",
        "Bash": "Running command",
        "Grep": "Searching code",
        "Glob": "Finding files",
        "WebFetch": "Fetching webpage",
        "WebSearch": "Searching the web",
        "Agent": "Launching agent",
        "NotebookEdit": "Editing notebook",
    }

    async def _execute_streaming(
        self,
        cmd: list[str],
        on_delta: Callable[[str], None] | None,
        on_status: Callable[[str], None] | None,
        timeout_seconds: float,
        session_id: str = "",
    ) -> tuple[str, str | None, dict | None]:
        """Run claude CLI and stream output.

        Returns (response_text, session_id, usage_dict).
        Reads raw chunks instead of readline() to avoid asyncio.StreamReader's
        64KB line-length limit — Claude's stream-json can emit arbitrarily large
        NDJSON lines (e.g. tool results containing entire file contents).
        """

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            start_new_session=True,  # own process group so killpg() reaches all children
        )
        # Track the subprocess so it can be killed on session end/reap
        if session_id:
            self._active_procs[session_id] = proc

        accumulated = ""
        claude_session_id = None
        usage = None
        last_activity = time.time()
        read_buf = ""  # partial-line buffer for chunk-based reading

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        proc.stdout.read(8192),
                        timeout=min(60.0, timeout_seconds - (time.time() - last_activity)),
                    )
                except asyncio.TimeoutError:
                    elapsed = time.time() - last_activity
                    if elapsed >= timeout_seconds:
                        _kill_process_tree(proc)
                        raise RuntimeError(f"Claude CLI timed out after {int(timeout_seconds)}s")
                    continue

                if not chunk:
                    # EOF — process any remaining partial line in the buffer
                    if read_buf.strip():
                        accumulated, claude_session_id, usage = self._process_ndjson_line(
                            read_buf.strip(), accumulated, claude_session_id, usage, on_delta, on_status
                        )
                    break

                last_activity = time.time()
                read_buf += chunk.decode(errors="ignore")

                # Split on newlines; last element is either "" or a partial line
                parts = read_buf.split("\n")
                read_buf = parts[-1]  # keep the incomplete trailing part

                for line_str in parts[:-1]:
                    line_str = line_str.strip()
                    if not line_str:
                        continue
                    accumulated, claude_session_id, usage = self._process_ndjson_line(
                        line_str, accumulated, claude_session_id, usage, on_delta, on_status
                    )

            await proc.wait()

            if proc.returncode != 0 and not accumulated:
                stderr = await proc.stderr.read()
                err_msg = stderr.decode(errors="ignore").strip()[:300]
                raise RuntimeError(f"Claude CLI exited with code {proc.returncode}: {err_msg}")

        except Exception:
            if proc.returncode is None:
                _kill_process_tree(proc)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except asyncio.TimeoutError:
                    pass
            raise
        finally:
            # Remove from active procs tracking
            if session_id:
                self._active_procs.pop(session_id, None)

        return accumulated, claude_session_id, usage

    def _process_ndjson_line(
        self,
        line_str: str,
        accumulated: str,
        claude_session_id: str | None,
        usage: dict | None,
        on_delta: Callable[[str], None] | None,
        on_status: Callable[[str], None] | None,
    ) -> tuple[str, str | None, dict | None]:
        """Parse a single NDJSON line and update state. Returns (accumulated, session_id, usage)."""
        try:
            event = json.loads(line_str)
        except json.JSONDecodeError:
            return accumulated, claude_session_id, usage

        event_type = event.get("type", "")

        if event_type == "assistant" and "message" in event:
            msg = event["message"]
            if isinstance(msg, dict):
                # Extract usage from message if present
                msg_usage = msg.get("usage")
                if msg_usage and isinstance(msg_usage, dict):
                    usage = {
                        "input_tokens": msg_usage.get("input_tokens", 0),
                        "output_tokens": msg_usage.get("output_tokens", 0),
                        "model": msg.get("model"),
                    }
                content = msg.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        # Only emit new text that wasn't already streamed via
                        # content_block_delta events.  Don't reset accumulated
                        # to this message's text — on multi-turn responses the
                        # assistant event only carries the current turn's text,
                        # while accumulated has all turns concatenated.
                        if len(text) > len(accumulated):
                            delta = text[len(accumulated):]
                            if delta and on_delta:
                                on_delta(delta)
                            accumulated = text
                        elif not accumulated.endswith(text) and text:
                            delta = text[len(accumulated):]
                            if delta and on_delta:
                                on_delta(delta)
                            accumulated = text
                    elif block.get("type") == "tool_use" and on_status:
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        label = self._TOOL_LABELS.get(tool_name, tool_name)
                        desc = ""
                        if tool_name in ("Read", "Write", "Edit"):
                            path = tool_input.get("file_path", "")
                            desc = path.split("/")[-1] if path else ""
                        elif tool_name == "Bash":
                            desc = tool_input.get("description", "")
                            cmd_str = tool_input.get("command", "")
                            if not desc:
                                desc = cmd_str[:60] if cmd_str else ""
                            elif cmd_str:
                                desc = f"{desc}\tcmd:{cmd_str[:200]}"
                        elif tool_name in ("Grep", "Glob"):
                            desc = tool_input.get("pattern", "")[:50]
                        elif tool_name == "Agent":
                            desc = tool_input.get("description", "")[:50]
                        elif tool_name in ("WebSearch", "WebFetch"):
                            desc = tool_input.get("query", tool_input.get("url", ""))[:50]
                        status_msg = f"{label}: {desc}" if desc else label
                        on_status(status_msg)

        elif event_type == "content_block_delta":
            delta_obj = event.get("delta", {})
            if delta_obj.get("type") == "text_delta":
                delta_text = delta_obj.get("text", "")
                if delta_text:
                    accumulated += delta_text
                    if on_delta:
                        on_delta(delta_text)

        elif event_type == "result":
            claude_session_id = event.get("session_id")
            result_text = event.get("result", "")
            if result_text:
                delta = result_text[len(accumulated):]
                if delta and on_delta:
                    on_delta(delta)
                accumulated = result_text
            # Extract usage from result event
            result_usage = event.get("usage")
            if result_usage and isinstance(result_usage, dict):
                usage = {
                    "input_tokens": result_usage.get("input_tokens", 0),
                    "output_tokens": result_usage.get("output_tokens", 0),
                    "model": event.get("model") or (usage or {}).get("model"),
                }
            # Also check for cost_usd or other token fields
            if not usage and event.get("num_turns"):
                # Fallback: log what fields are available for future use
                logger.debug("Result event keys (no usage): %s", list(event.keys()))

        return accumulated, claude_session_id, usage

    async def prune_stale(self, max_age_seconds: float = 21600) -> None:
        """Remove sessions idle for longer than max_age_seconds."""
        now = time.time()
        async with self._lock:
            stale = [
                sid for sid, s in self._sessions.items()
                if now - s.last_used > max_age_seconds
            ]
            for sid in stale:
                logger.info("[%s] Pruning stale persistent Claude session", sid[:12])
                del self._sessions[sid]
                proc = self._active_procs.pop(sid, None)
                if proc and proc.returncode is None:
                    _kill_process_tree(proc)


# Singleton
_manager: ClaudePersistentManager | None = None


def get_claude_persistent_manager() -> ClaudePersistentManager:
    global _manager
    if _manager is None:
        _manager = ClaudePersistentManager()
    return _manager
