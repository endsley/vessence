"""Single source of truth for the local LLM Jane's v2 pipeline uses.

The 3-stage pipeline vocabulary:
  - Stage 1 → classifier (ChromaDB k-NN, no LLM)
  - Stage 2 → class action handlers
  - Stage 3 → final brain (Opus / Claude / Gemini)

Several Stage 2 handlers, the dispatcher's gate check, and the Stage 3
ack generator all delegate to the *same* local LLM running under Ollama.
This module exports that choice as one constant so a swap is a one-line
change instead of a grep-and-replace.

Override via env: JANE_LOCAL_LLM=<ollama_tag>
(legacy alias JANE_STAGE2_MODEL still honored for backward compatibility)
"""

from __future__ import annotations

import os

#: The Ollama tag every component (handlers, gate check, ack generator,
#: startup warmup) talks to.
LOCAL_LLM: str = os.environ.get(
    "JANE_LOCAL_LLM",
    os.environ.get("JANE_STAGE2_MODEL", "qwen2.5:7b"),  # legacy env name
)

#: Base URL for Ollama's HTTP API.
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

#: keep_alive value passed with every local-LLM request. `-1` pins the
#: model in Ollama's memory indefinitely so users never hit a cold-load
#: stall after an idle period.
OLLAMA_KEEP_ALIVE: int = -1
