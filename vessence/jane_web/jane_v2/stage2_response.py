"""Stage 2 response formatting helpers."""

from __future__ import annotations

import re
from typing import Any

from jane_web.client_tool_markers import visible_text_and_client_tool_calls
from jane_web.music_playlists import music_play_marker


_STAGE2_MARKER_RE = re.compile(
    r"\[\[CLIENT_TOOL:|\[\[AWAITING:|\[MUSIC_PLAY:|\[TOOL_RESULT:"
)


def assemble_music_text(result: dict) -> str:
    """Append ``[MUSIC_PLAY:<id>]`` when the handler returned a playlist id."""
    text = result.get("text", "")
    playlist_id = result.get("playlist_id")
    if playlist_id and "[MUSIC_PLAY:" not in text:
        text = text.rstrip() + f" {music_play_marker(playlist_id)}"
    return text


def wrap_spoken(text: str) -> str:
    """Wrap the speakable prefix of a Stage 2 reply in ``<spoken>`` tags."""
    if not text or "<spoken>" in text:
        return text
    match = _STAGE2_MARKER_RE.search(text)
    if match is None:
        return f"<spoken>{text.strip()}</spoken>"
    spoken_part = text[:match.start()].strip()
    rest = text[match.start():].strip()
    if not spoken_part:
        return rest
    return f"<spoken>{spoken_part}</spoken> {rest}"


def stage2_response_parts(result: dict) -> tuple[str, dict[str, Any]]:
    """Normalize a Stage 2 handler result into ``(visible_text, extras)``."""
    text = wrap_spoken(assemble_music_text(result))
    if result.get("print"):
        text = text.rstrip() + "\n\n" + result["print"]

    extras: dict[str, Any] = {}
    if result.get("playlist_id"):
        extras["playlist_id"] = result["playlist_id"]
        extras["playlist_name"] = result.get("playlist_name")
    if result.get("client_tools"):
        extras["client_tools"] = result["client_tools"]
    if result.get("conversation_end"):
        extras["conversation_end"] = True
    return text, extras


def stage2_visible_text_and_client_tool_calls(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip embedded client-tool markers and return structured tool calls."""
    return visible_text_and_client_tool_calls(text)
