"""Intent Classifier v3 — FIFO-aware LLM-backed classifier (Haiku).

Replaces the v2 two-step gate+handler dance with a single classification
call that sees: (a) the ChromaDB embedding's top-K candidates, (b) the
recent conversation FIFO, and (c) each candidate class's definition.
The LLM returns one of those candidate classes plus a confidence level.
The pipeline then routes High-confidence + handler-present turns to
Stage 2 and everything else to Stage 3 (Opus).

Keeps v1/v2 untouched. v3 is opt-in via JANE_USE_V3_PIPELINE=1 in .env.
"""
