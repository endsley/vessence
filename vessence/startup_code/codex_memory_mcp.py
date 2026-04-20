#!/usr/bin/env python3
"""Codex MCP bridge for Jane's live ChromaDB memory.

Codex does not currently provide Claude Code-style UserPromptSubmit hooks on
this machine. This stdio MCP server gives Codex sessions an explicit
`query_jane_memory` tool backed by the same live ChromaDB retrieval layer used
by Jane/Claude hooks.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP


VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data"))
VAULT_HOME = Path(os.environ.get("VAULT_HOME", "/home/chieh/ambient/vault"))

if str(VESSENCE_HOME) not in sys.path:
    sys.path.insert(0, str(VESSENCE_HOME))

mcp = FastMCP("jane-memory")


def _strip_onnx_noise(text: str) -> str:
    """Remove common ONNX provider fallback noise from helper output."""
    blocked = (
        "***",
        "EP Error",
        "Falling back",
        "when using [",
    )
    noisy_terms = (
        "TensorrtExecutionProvider",
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
        "libonnxruntime_providers_tensorrt",
    )
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in blocked):
            continue
        if any(term in stripped for term in noisy_terms):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


class _silence_process_output:
    """Temporarily route process stdout/stderr to /dev/null.

    SentenceTransformer and Chroma dependencies can write directly to file
    descriptors, bypassing Python's sys.stdout/sys.stderr. Since MCP stdio uses
    stdout for protocol messages, retrieval must be quiet at the fd level.
    """

    def __enter__(self):
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)


@mcp.tool()
def query_jane_memory(query: str, max_chars: int = 12000) -> str:
    """Query Jane's live ChromaDB memory for relevant context.

    Use this before answering questions about Chieh, Jane/Vessence history,
    recent decisions, preferences, project state, or anything phrased as
    "remember", "recently", "what did we decide", or "what was the reason".
    """
    q = (query or "").strip()
    if not q:
        return "No query provided."
    try:
        # The embedding stack can print progress bars and provider warnings to
        # stdout. MCP stdio uses stdout for JSON-RPC, so silence all retrieval
        # chatter and return only the memory payload.
        with _silence_process_output():
            from memory.v1.memory_retrieval import build_memory_sections

            sections = build_memory_sections(q, assistant_name="Jane")
    except Exception as exc:
        return f"Memory query failed: {type(exc).__name__}: {exc}"
    if not sections:
        return "No relevant context found."
    text = _strip_onnx_noise("\n\n".join(sections))
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n...[truncated]"
    return text or "No relevant context found."


@mcp.tool()
def jane_memory_paths() -> str:
    """Return the configured Jane memory roots for this Codex session."""
    return (
        f"VESSENCE_HOME={VESSENCE_HOME}\n"
        f"VESSENCE_DATA_HOME={VESSENCE_DATA_HOME}\n"
        f"VAULT_HOME={VAULT_HOME}\n"
        f"vector_db={VESSENCE_DATA_HOME / 'vector_db'}"
    )


if __name__ == "__main__":
    mcp.run()
