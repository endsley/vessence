"""Text chunking helpers for chat TTS generation."""

from __future__ import annotations

import re


def split_tts_chunks(text: str, max_chars: int = 150) -> list[str]:
    """Split text into sentence-level chunks for XTTS-v2 (~20s max per chunk)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 <= max_chars:
            current += " " + sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_chars:
                for part in re.split(r",\s*", sentence):
                    if current and len(current) + len(part) + 2 <= max_chars:
                        current += ", " + part
                    else:
                        if current:
                            chunks.append(current)
                        current = part
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]
