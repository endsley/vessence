"""Tiny shim around ChromaDB's default embedding function so writers can
embed a transformation of the document (e.g. label-stripped search text)
while keeping the labeled form as the displayed document.

Used by both short-term writers (Jane web's ``conversation_manager`` and
the Claude Code Stop hook ``claude_stop_short_term``) so retrieval
embeddings reflect content semantics, not labeled-bullet boilerplate.

The embedding function is module-level cached so we pay the model load
cost once per process.
"""
from __future__ import annotations

from typing import Sequence

_ef = None


def _get_ef():
    global _ef
    if _ef is None:
        from chromadb.utils import embedding_functions
        _ef = embedding_functions.DefaultEmbeddingFunction()
    return _ef


def embed_one(text: str) -> list[float]:
    """Embed a single string with the same model ChromaDB uses by default.

    Returns a Python list of floats (Chroma accepts that shape directly
    in ``add(embeddings=...)``).
    """
    return _get_ef()([text])[0]


def embed_many(texts: Sequence[str]) -> list[list[float]]:
    """Embed multiple strings in one call (cheaper than calling
    ``embed_one`` in a loop)."""
    return _get_ef()(list(texts))
