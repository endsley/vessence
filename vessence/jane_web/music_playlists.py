"""Music playlist query and matching helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


RANDOM_MUSIC_QUERIES = {
    "random", "anything", "something", "a song", "music",
    "random song", "some music", "something random",
}
MUSIC_QUERY_PREFIX_RE = re.compile(
    r"^(play|put on|start|queue up|shuffle|resume|i want to (listen to|hear)|"
    r"i'?d like to (listen to|hear))\s+"
)
MUSIC_QUERY_ARTICLE_RE = re.compile(r"^(some |the |my |a |an )+")
MUSIC_QUERY_SUFFIX_RE = re.compile(r"\s+(playlist|folder|music|songs?)$")
MUSIC_PLAY_MARKER_RE = re.compile(r"\[MUSIC_PLAY:([^\]]+)\]")
MUSIC_PLAYLIST_ID_RE = re.compile(r"^[0-9a-f]{16}$")
MUSIC_STOPWORDS = {
    "a", "an", "the", "by", "of", "in", "on", "to", "for", "and", "or",
    "is", "it", "my", "me", "we", "do", "have", "any", "some", "from",
    "song", "songs", "music", "play", "playing", "listen", "track", "tracks",
    "album", "artist", "something", "anything", "like", "want", "hear",
}


@dataclass(frozen=True)
class MusicQueryParts:
    raw: str
    q: str
    q_norm: str
    q_core: str
    is_random: bool


@dataclass(frozen=True)
class MusicPlayMarker:
    marker: str
    query: str


def normalize_music_query(query: str) -> MusicQueryParts:
    q = (query or "").strip().lower()
    q_norm = re.sub(r"\s+", " ", q)
    q_core = MUSIC_QUERY_PREFIX_RE.sub("", q_norm)
    q_core = MUSIC_QUERY_ARTICLE_RE.sub("", q_core)
    q_core = MUSIC_QUERY_SUFFIX_RE.sub("", q_core).strip()
    return MusicQueryParts(query, q, q_norm, q_core, q_norm in RANDOM_MUSIC_QUERIES)


def extract_fallback_music_play_marker(payload: str | None) -> MusicPlayMarker | None:
    """Return a non-playlist-id MUSIC_PLAY marker that needs fallback playlist creation."""
    match = MUSIC_PLAY_MARKER_RE.search(payload or "")
    if not match:
        return None
    query = match.group(1).strip()
    if MUSIC_PLAYLIST_ID_RE.match(query):
        return None
    return MusicPlayMarker(marker=match.group(0), query=query)


def music_play_marker(playlist_id: str) -> str:
    return f"[MUSIC_PLAY:{playlist_id}]"


def replace_music_play_marker(payload: str, marker: MusicPlayMarker, playlist_id: str) -> str:
    return payload.replace(marker.marker, music_play_marker(playlist_id))


def is_temporary_playlist_name(name: str) -> bool:
    return name == "Random Mix" or name.startswith("Playing:")


def should_delete_temporary_playlist(playlist: dict[str, Any], cutoff: str) -> bool:
    return is_temporary_playlist_name(playlist.get("name", "")) and playlist.get("created_at", "") < cutoff


def real_user_playlists(playlists: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        playlist for playlist in playlists
        if not is_temporary_playlist_name(playlist.get("name", ""))
    ]


def _playlist_name_norm(playlist: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", playlist.get("name", "").lower())


def _token_set_ratio(left: str, right: str) -> int | None:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return None
    return int(fuzz.token_set_ratio(left, right))


def find_matching_playlist(
    q_core: str,
    playlists: Iterable[dict[str, Any]],
    *,
    scorer: Callable[[str, str], int | float | None] | None = None,
    threshold: int = 80,
) -> dict[str, Any] | None:
    if not q_core:
        return None
    real = list(playlists)
    for playlist in real:
        if _playlist_name_norm(playlist) == q_core:
            return playlist
    for playlist in real:
        name_norm = _playlist_name_norm(playlist)
        if not name_norm:
            continue
        if q_core in name_norm or name_norm in q_core:
            return playlist
    score_fn = scorer or _token_set_ratio
    scored = [
        (score_fn(q_core, _playlist_name_norm(playlist)), playlist)
        for playlist in real
        if playlist.get("name", "")
    ]
    scored = [(score, playlist) for score, playlist in scored if score is not None]
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= threshold:
        return scored[0][1]
    return None


def content_words(query: str) -> list[str]:
    return [word for word in query.split() if word not in MUSIC_STOPWORDS and len(word) > 1]


def _filename_lower(path: str) -> str:
    return path.lower().split("/")[-1].lower()


def select_music_files(
    query: str,
    all_files: list[str],
    *,
    scorer: Callable[[str, str], int | float | None] | None = None,
) -> list[str]:
    selected = [path for path in all_files if query in _filename_lower(path)]
    if selected:
        return selected

    words = content_words(query)
    if words:
        selected = [
            path for path in all_files
            if all(word in _filename_lower(path) for word in words)
        ]
    if selected:
        return selected

    if words:
        selected = [
            path for path in all_files
            if any(word in _filename_lower(path) for word in words)
        ]
    if selected:
        return selected

    score_fn = scorer or _token_set_ratio
    scored = []
    for path in all_files:
        filename = Path(path).stem.lower()
        score = score_fn(query, filename)
        if score is not None and score >= 60:
            scored.append((score, path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored[:10]]


def playlist_name_for_query(parts: MusicQueryParts) -> str:
    return "Random Mix" if parts.is_random else f"Playing: {parts.q.title()}"


def playlist_tracks(filepaths: list[str], *, vault_parent: Path) -> list[dict[str, str]]:
    tracks = []
    for filepath in filepaths:
        path = Path(filepath)
        tracks.append({"path": str(path.relative_to(vault_parent)), "title": path.stem})
    return tracks
