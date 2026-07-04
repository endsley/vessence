"""Music playlist query and matching helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
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


def playlist_track_names(playlist: dict[str, Any], *, limit: int = 10) -> str:
    return ", ".join(
        track.get("title", track.get("path", "?"))
        for track in playlist["tracks"][:limit]
    )


def music_playlist_task_context(playlist: dict[str, Any]) -> str:
    return (
        f"[MUSIC DATA]\n"
        f"Playlist ID: {playlist['id']}\n"
        f"Name: {playlist['name']}\n"
        f"Tracks ({len(playlist['tracks'])}): {playlist_track_names(playlist)}\n"
        f"[END MUSIC DATA]"
    )


def music_playlist_delegate_context(playlist: dict[str, Any]) -> str:
    return (
        f"\n\n[MUSIC DATA \u2014 playlist created server-side]\n"
        f"Playlist ID: {playlist['id']}\n"
        f"Name: {playlist['name']}\n"
        f"Tracks ({len(playlist['tracks'])}): {playlist_track_names(playlist)}\n"
        f"[END MUSIC DATA]\n\n"
        f"To play this playlist, include {music_play_marker(playlist['id'])} in your response.\n"
        f"Tell the user what you're playing. If tracks include duplicates or "
        f"unwanted versions (e.g., tutorials vs originals), mention it."
    )


def music_playlist_no_match_task_context() -> str:
    return "[MUSIC DATA]\nNo matching tracks found.\n[END MUSIC DATA]"


def music_playlist_no_match_delegate_context() -> str:
    return (
        "\n\n[MUSIC DATA]\n"
        "No matching tracks found for this query.\n"
        "[END MUSIC DATA]\n"
        "Tell the user you couldn't find matching music."
    )


def music_playlist_task_error_context(error: Exception) -> str:
    return f"[MUSIC ERROR]\n{error}\n[END MUSIC ERROR]"


def music_playlist_delegate_error_context(error: Exception) -> str:
    return (
        f"\n\n[MUSIC ERROR]\n"
        f"Failed to search music library: {error}\n"
        f"[END MUSIC ERROR]"
    )


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


def _exact_playlist_match(q_core: str, playlists: list[dict[str, Any]]) -> dict[str, Any] | None:
    for playlist in playlists:
        if _playlist_name_norm(playlist) == q_core:
            return playlist
    return None


def _substring_playlist_match(q_core: str, playlists: list[dict[str, Any]]) -> dict[str, Any] | None:
    for playlist in playlists:
        name_norm = _playlist_name_norm(playlist)
        if not name_norm:
            continue
        if q_core in name_norm or name_norm in q_core:
            return playlist
    return None


def _token_set_ratio(left: str, right: str) -> int | None:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return None
    return int(fuzz.token_set_ratio(left, right))


def _scored_playlist_matches(
    q_core: str,
    playlists: list[dict[str, Any]],
    score_fn: Callable[[str, str], int | float | None],
) -> list[tuple[int | float, dict[str, Any]]]:
    scored = [
        (score_fn(q_core, _playlist_name_norm(playlist)), playlist)
        for playlist in playlists
        if playlist.get("name", "")
    ]
    scored = [(score, playlist) for score, playlist in scored if score is not None]
    return sorted(scored, key=lambda item: item[0], reverse=True)


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
    exact = _exact_playlist_match(q_core, real)
    if exact is not None:
        return exact
    substring = _substring_playlist_match(q_core, real)
    if substring is not None:
        return substring
    score_fn = scorer or _token_set_ratio
    scored = _scored_playlist_matches(q_core, real, score_fn)
    if scored and scored[0][0] >= threshold:
        return scored[0][1]
    return None


def content_words(query: str) -> list[str]:
    return [word for word in query.split() if word not in MUSIC_STOPWORDS and len(word) > 1]


def _filename_lower(path: str) -> str:
    return path.lower().split("/")[-1].lower()


def _files_with_query_in_filename(query: str, all_files: list[str]) -> list[str]:
    return [path for path in all_files if query in _filename_lower(path)]


def _files_with_all_words(words: list[str], all_files: list[str]) -> list[str]:
    return [
        path for path in all_files
        if all(word in _filename_lower(path) for word in words)
    ]


def _files_with_any_word(words: list[str], all_files: list[str]) -> list[str]:
    return [
        path for path in all_files
        if any(word in _filename_lower(path) for word in words)
    ]


def _scored_music_files(
    query: str,
    all_files: list[str],
    score_fn: Callable[[str, str], int | float | None],
    *,
    threshold: int = 60,
    limit: int = 10,
) -> list[str]:
    scored = []
    for path in all_files:
        filename = Path(path).stem.lower()
        score = score_fn(query, filename)
        if score is not None and score >= threshold:
            scored.append((score, path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored[:limit]]


def select_music_files(
    query: str,
    all_files: list[str],
    *,
    scorer: Callable[[str, str], int | float | None] | None = None,
) -> list[str]:
    selected = _files_with_query_in_filename(query, all_files)
    if selected:
        return selected

    words = content_words(query)
    if words:
        selected = _files_with_all_words(words, all_files)
    if selected:
        return selected

    if words:
        selected = _files_with_any_word(words, all_files)
    if selected:
        return selected

    score_fn = scorer or _token_set_ratio
    return _scored_music_files(query, all_files, score_fn)


def playlist_name_for_query(parts: MusicQueryParts) -> str:
    return "Random Mix" if parts.is_random else f"Playing: {parts.q.title()}"


def playlist_tracks(filepaths: list[str], *, vault_parent: Path) -> list[dict[str, str]]:
    tracks = []
    for filepath in filepaths:
        path = Path(filepath)
        tracks.append({"path": str(path.relative_to(vault_parent)), "title": path.stem})
    return tracks


def cleanup_temporary_playlists(
    *,
    list_playlists_fn: Callable[[], list[dict[str, Any]]],
    delete_playlist_fn: Callable[[str], Any],
    now_fn: Callable[[], datetime] = datetime.now,
    logger: Any | None = None,
) -> None:
    """Delete generated music playlists older than the Android fetch grace window."""
    try:
        cutoff = (now_fn() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        for playlist in list_playlists_fn():
            if should_delete_temporary_playlist(playlist, cutoff):
                delete_playlist_fn(playlist["id"])
    except Exception as exc:
        if logger is not None:
            logger.warning("temporary playlist cleanup failed: %s", exc)


def existing_playlist_for_music_query(
    query_parts: MusicQueryParts,
    *,
    original_query: str,
    list_playlists_fn: Callable[[], list[dict[str, Any]]],
    get_playlist_fn: Callable[[str], dict[str, Any] | None],
    logger: Any | None = None,
) -> dict[str, Any] | None:
    if not query_parts.q_core or query_parts.is_random:
        return None
    try:
        existing = list_playlists_fn()
    except Exception:
        existing = []
    hit = find_matching_playlist(query_parts.q_core, real_user_playlists(existing))
    if hit is None:
        return None
    full = get_playlist_fn(hit["id"])
    if not full:
        return None
    if logger is not None:
        logger.info(
            "music query %r matched existing playlist %r (%d tracks) — Tier 0 hit",
            original_query,
            hit.get("name", ""),
            len(full.get("tracks", []) or []),
        )
    full["temporary"] = False
    return full


def music_playlist_from_query(
    query: str,
    *,
    list_playlists_fn: Callable[[], list[dict[str, Any]]],
    get_playlist_fn: Callable[[str], dict[str, Any] | None],
    create_playlist_fn: Callable[[str, list[dict[str, str]]], dict[str, Any]],
    delete_playlist_fn: Callable[[str], Any],
    vault_home: str | Path,
    glob_files_fn: Callable[..., list[str]],
    random_sample_fn: Callable[[list[str], int], list[str]],
    logger: Any | None = None,
) -> dict[str, Any] | None:
    cleanup_temporary_playlists(
        list_playlists_fn=list_playlists_fn,
        delete_playlist_fn=delete_playlist_fn,
        logger=logger,
    )
    query_parts = normalize_music_query(query)

    existing = existing_playlist_for_music_query(
        query_parts,
        original_query=query,
        list_playlists_fn=list_playlists_fn,
        get_playlist_fn=get_playlist_fn,
        logger=logger,
    )
    if existing is not None:
        return existing

    vault_music = Path(vault_home) / "Music"
    all_files = sorted(glob_files_fn(str(vault_music / "**" / "*.mp3"), recursive=True))
    if not all_files:
        return None

    if query_parts.is_random:
        selected = random_sample_fn(all_files, min(10, len(all_files)))
    else:
        selected = select_music_files(query_parts.q, all_files)
        if not selected:
            return None

    playlist_name = playlist_name_for_query(query_parts)
    tracks = playlist_tracks(selected, vault_parent=vault_music.parent)
    playlist = create_playlist_fn(playlist_name, tracks)
    playlist["temporary"] = True
    return playlist
