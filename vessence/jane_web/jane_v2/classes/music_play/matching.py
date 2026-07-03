"""Pure playlist matching helpers for the music-play handler."""
from __future__ import annotations

from collections.abc import Callable
import re

from jane_web.music_playlists import music_play_marker


ACTIONABLE_KINDS = {"shuffle", "song", "artist", "playlist", "genre", "mood"}
FUZZY_MATCH_THRESHOLD = 80


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower().strip())


def select_playlist_candidate(
    query: str,
    candidates: list[dict],
    score_func: Callable[[str, str], float] | None = None,
) -> dict | None:
    """Return the best candidate by exact, substring, then fuzzy name match."""
    query_norm = normalize(query)
    if not query_norm or not candidates:
        return None

    for candidate in candidates:
        if normalize(candidate.get("name", "")) == query_norm:
            return candidate

    for candidate in candidates:
        name = normalize(candidate.get("name", ""))
        if not name:
            continue
        if query_norm in name or name in query_norm:
            return candidate

    if score_func is None:
        return None

    scored = []
    for candidate in candidates:
        name = normalize(candidate.get("name", ""))
        if not name:
            continue
        score = score_func(query_norm, name)
        if score >= FUZZY_MATCH_THRESHOLD:
            scored.append((score, candidate))
    if not scored:
        return None
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored[0][1]


def format_play_response(playlist: dict) -> dict:
    name = playlist.get("name", "that playlist")
    tracks = playlist.get("tracks", []) or []
    playlist_id = playlist.get("id")
    text = f"Playing {name} ({len(tracks)} tracks)."
    if playlist_id:
        text = text.rstrip() + f" {music_play_marker(playlist_id)}"
    return {"text": text, "playlist_id": playlist_id, "playlist_name": name}
