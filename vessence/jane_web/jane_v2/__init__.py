"""jane_v2 — 3-stage Jane pipeline (classifier → per-class handler → Opus).

Activated via env var JANE_PIPELINE=v2. When unset (or set to v1),
main.py falls through to the existing v1 code path and this package is
never imported.

Stages:
  1. stage1_classifier — ChromaDB embedding k-NN routes the prompt to a class
     (weather, music play, others) with High/Medium/Low confidence.
  2. stage2_* handlers — per-class handlers produce a direct answer
     when confidence is High.
  3. Stage 3 (fallback) — anything the handlers cannot answer is
     delegated to the existing v1 stream_message / send_message brain.
"""
