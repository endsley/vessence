"""jane_v3 — simplified Jane pipeline.

v3 collapses v2's three independent state machines (Stage 1 embedding,
Stage 2 gate + continuation checks, pending_action_resolver routing) into
a single FIFO-aware classification call (Haiku via persistent CLI). The
per-class handlers from jane_v2 are reused unchanged.

Entry points (drop-in replacements for jane_v2):
  handle_chat(body, request)         → non-streaming /api/jane/chat
  handle_chat_stream(body, request)  → streaming   /api/jane/chat/stream

Opt-in via JANE_USE_V3_PIPELINE=1 in .env. When the flag is absent, jane_v2
serves every request and v3 imports nothing.
"""
