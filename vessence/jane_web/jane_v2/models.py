"""Single source of truth for ALL local LLM model references.

Every Python file that calls Ollama should import from HERE, never
hardcode a model tag. To swap a model, change ONE line in this file.

The 3-stage pipeline vocabulary:
  - Stage 1 → classifier (ChromaDB k-NN, no LLM)
  - Stage 2 → class action handlers, gate check, ack generator
  - Stage 3 → final brain (Opus / Claude / Gemini)

Environment overrides:
  JANE_LOCAL_LLM        → STAGE2_MODEL (primary override)
  JANE_STAGE2_MODEL     → STAGE2_MODEL (legacy alias)
  JANE_SUMMARIZER_MODEL → SUMMARIZER_MODEL
  JANE_AUDIT_JUDGE_MODEL → AUDIT_JUDGE_MODEL
  OLLAMA_URL            → OLLAMA_URL
"""

from __future__ import annotations

import os

# ─── Model tags ──────────────────��────────────────────────────────────────────
# Change the default here to swap globally. Every file imports from this
# module — no grep-and-replace needed.

#: Stage 2 handlers, gate check, ack generator, startup warmup.
STAGE2_MODEL: str = os.environ.get(
    "JANE_LOCAL_LLM",
    os.environ.get("JANE_STAGE2_MODEL", "qwen2.5:7b"),
)

#: Stop-hook summarizer (shares Stage 2 model).
SUMMARIZER_MODEL: str = os.environ.get("JANE_SUMMARIZER_MODEL", STAGE2_MODEL)

#: Pipeline audit judge (nightly self-improve).
AUDIT_JUDGE_MODEL: str = os.environ.get("JANE_AUDIT_JUDGE_MODEL", STAGE2_MODEL)

#: Briefing news summarizer.
BRIEFING_MODEL: str = os.environ.get("BRIEFING_SUMMARY_MODEL", STAGE2_MODEL)

# Backward-compatible alias — older code imported LOCAL_LLM.
LOCAL_LLM = STAGE2_MODEL

# ─── Ollama settings ──────────────────────────────��──────────────────────────

#: Base URL for Ollama's HTTP API.
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

#: keep_alive value passed with every local-LLM request. `-1` pins the
#: model in Ollama's memory indefinitely so users never hit a cold-load
#: stall after an idle period.
OLLAMA_KEEP_ALIVE: int = -1

#: Context window for ALL local-LLM callers. Ollama runs a separate runner
#: per (model, num_ctx) tuple — if one caller uses 1024 and another uses
#: 32768 with the same model, Ollama will evict/reload on every switch,
#: causing ~1.5-3s cold-start stalls per swap. Every production file that
#: posts to /api/generate or /api/chat against this model MUST import and
#: use this constant. 8192 gives summarizers/audits room for long inputs
#: and gemma_router headroom for history, while still fitting comfortably
#: in VRAM (KV cache ≈ 448 MiB at this size — well under our GPU budget).
LOCAL_LLM_NUM_CTX: int = int(os.environ.get("JANE_LOCAL_LLM_NUM_CTX", "8192"))

#: Shared local-LLM timeout. Long enough for a cold load, still bounded.
LOCAL_LLM_TIMEOUT: float = float(os.environ.get("JANE_STAGE2_TIMEOUT", "12.0"))
