"""TTS response contract helpers for Jane proxy responses."""

from __future__ import annotations

import logging
import re as _re


logger = logging.getLogger("jane.proxy")

_TTS_SPOKEN_BLOCK_RE = _re.compile(
    r"<spoken>(.*?)</spoken>",
    _re.IGNORECASE | _re.DOTALL,
)
_TTS_SPOKEN_TAG_RE = _re.compile(r"</?(?:spoken|visual|think|thinking|artifact)>", _re.IGNORECASE)
_TTS_CLIENT_TOOL_MARKER_RE = _re.compile(r"\[\[CLIENT_TOOL:[a-z][a-z0-9_.]*:\{[\s\S]*?\}\]\]", _re.IGNORECASE)
_TTS_MUSIC_PLAY_RE = _re.compile(r"\[MUSIC_PLAY:[^\]]+\]")
_TTS_SENTENCE_RE = _re.compile(r"[^.!?]+[.!?]?", _re.DOTALL)
_TTS_ABBREVIATIONS = (
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "St.",
    "Jr.",
    "Sr.",
    "vs.",
    "e.g.",
    "i.e.",
    "etc.",
)
_TTS_SPOKEN_SENTENCE_LIMIT = 2
_TTS_SPOKEN_MAX_CHARS = 220
_TTS_SPOKEN_MAX_WORDS = 28


def normalize_tts_text(raw: str) -> str:
    if not raw:
        return ""
    text = _TTS_SPOKEN_TAG_RE.sub("", raw)
    text = _TTS_CLIENT_TOOL_MARKER_RE.sub("", text)
    text = _TTS_MUSIC_PLAY_RE.sub("", text)
    return _re.sub(r"\s+", " ", text).strip(" \t\r\n-—–")


def split_tts_sentences(text: str) -> list[str]:
    protected = text or ""
    for abbr in _TTS_ABBREVIATIONS:
        pattern = _re.compile(_re.escape(abbr), _re.IGNORECASE)
        protected = pattern.sub(lambda m: m.group(0).replace(".", "<DOT>"), protected)
    return [
        sentence.replace("<DOT>", ".").strip()
        for sentence in _TTS_SENTENCE_RE.findall(protected)
        if sentence.strip()
    ]


def take_short_tts_spoken(raw: str) -> tuple[str, str]:
    compact = normalize_tts_text(raw)
    if not compact:
        return "", ""
    sentences = split_tts_sentences(compact)
    if not sentences:
        return compact, ""
    spoken_part = " ".join(sentences[:_TTS_SPOKEN_SENTENCE_LIMIT]).strip()
    detail_part = " ".join(sentences[_TTS_SPOKEN_SENTENCE_LIMIT:]).strip()
    spoken_part = truncate_tts_spoken_text(spoken_part)
    return spoken_part, detail_part


def truncate_tts_spoken_text(text: str) -> str:
    text = normalize_tts_text(text)
    if not text:
        return ""
    words = text.split()
    if len(words) > _TTS_SPOKEN_MAX_WORDS:
        text = " ".join(words[:_TTS_SPOKEN_MAX_WORDS])
    if len(text) <= _TTS_SPOKEN_MAX_CHARS:
        return text
    hard = text[: _TTS_SPOKEN_MAX_CHARS].rstrip()
    cut = hard.rfind(" ")
    if cut > 60:
        hard = hard[:cut].rstrip()
    if not hard:
        hard = text[: _TTS_SPOKEN_MAX_CHARS].rstrip()
    if not hard.endswith((".", "!", "?")):
        hard = hard.rstrip(",;:") + "…"
    if len(hard) > _TTS_SPOKEN_MAX_CHARS:
        hard = hard[: _TTS_SPOKEN_MAX_CHARS]
    return hard


def combine_tts_detail(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p).strip()


def enforce_tts_output_contract(response: str, session_id: str, source: str) -> str:
    raw = (response or "").strip()
    if not raw:
        return raw

    spoken_match = _TTS_SPOKEN_BLOCK_RE.search(raw)
    if spoken_match:
        spoken_source = spoken_match.group(1) or ""
        preface = raw[:spoken_match.start()].strip()
        trailing = raw[spoken_match.end() :].strip()
        if preface:
            spoken_source = f"{preface} {spoken_source}"
    else:
        spoken_source = raw
        trailing = ""

    spoken_text, trailing_from_spoken = take_short_tts_spoken(spoken_source)
    trailing = combine_tts_detail(trailing_from_spoken, trailing)
    trailing = normalize_tts_text(trailing)

    if not spoken_text:
        spoken_text = "Got it."

    enforced = f"<spoken>{spoken_text}</spoken>"
    if trailing:
        enforced = f"{enforced}\n\n{trailing}"

    if enforced != raw:
        logger.warning(
            "[%s] TTS contract enforcement (%s): normalized response. raw_len=%d enforced_len=%d",
            session_id[:12],
            source,
            len(raw),
            len(enforced),
        )
    return enforced
