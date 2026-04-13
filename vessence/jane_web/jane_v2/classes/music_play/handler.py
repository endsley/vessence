"""Music play Stage 2 handler.

Resolves a play request into an actual playlist using a tiered strategy:

  1. Exact / fuzzy match against existing named user playlists. If found,
     return that playlist.
  2. Fall through to v1's resolver (create_music_playlist_from_query in
     jane_web.main) which walks the music library and builds an ephemeral
     playlist.

Returns a dict the pipeline can merge into its response:
    {
        "text": "Playing coldplay (6 tracks). [MUSIC_PLAY:<id>]",
        "playlist_id": "<id>",
        "playlist_name": "<name>",
    }

The `[MUSIC_PLAY:<id>]` marker is appended to the text so Android and
the web UI can detect it and auto-start playback without any new fields.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _extract_query(user_prompt: str) -> str:
    """Strip common request wrappers so we match the core name."""
    p = _normalize(user_prompt)
    p = re.sub(r"^(can you |could you |please |jane,? |hey jane,? )+", "", p)
    p = re.sub(
        r"^(play|put on|start|queue up|shuffle|resume|i want to (listen to|hear)|"
        r"i'?d like to (listen to|hear))\s+",
        "",
        p,
    )
    p = re.sub(r"^(some |the |my |a |an )+", "", p)
    p = re.sub(r"\s+(playlist|folder|music|songs?)$", "", p)
    return p.strip() or _normalize(user_prompt)


def _match_existing_playlist(query: str) -> dict | None:
    """Return a playlist dict if the query matches an existing user playlist."""
    try:
        from vault_web.playlists import list_playlists, get_playlist
    except Exception as e:
        logger.warning("music handler: vault_web.playlists import failed: %s", e)
        return None

    q = _normalize(query)
    if not q:
        return None

    candidates = list_playlists()
    if not candidates:
        return None

    # Tier A — exact (case-insensitive) match
    for p in candidates:
        if _normalize(p.get("name", "")) == q:
            return get_playlist(p["id"])

    # Tier B — substring either way
    for p in candidates:
        name = _normalize(p.get("name", ""))
        if not name:
            continue
        if q in name or name in q:
            return get_playlist(p["id"])

    # Tier C — fuzzy match via rapidfuzz
    try:
        from rapidfuzz import fuzz

        scored = []
        for p in candidates:
            name = _normalize(p.get("name", ""))
            if not name:
                continue
            score = fuzz.token_set_ratio(q, name)
            if score >= 80:
                scored.append((score, p))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return get_playlist(scored[0][1]["id"])
    except ImportError:
        pass

    return None


def _ephemeral_from_library(query: str) -> dict | None:
    """Fall back to v1's library scanner + ephemeral playlist builder."""
    try:
        from jane_web.main import create_music_playlist_from_query
    except Exception as e:
        logger.warning("music handler: could not import v1 resolver: %s", e)
        return None
    return create_music_playlist_from_query(query)


def handle(prompt: str) -> dict | None:
    """Resolve a music-play request and return a dict the pipeline can return.

    Sync on purpose — the pipeline offloads this to a thread because the
    underlying playlist resolver does DB and filesystem work.
    """
    query = _extract_query(prompt)
    logger.info("music handler: query=%r", query)

    existing = _match_existing_playlist(query)
    if existing:
        name = existing.get("name", "that playlist")
        tracks = existing.get("tracks", []) or []
        pid = existing.get("id")
        logger.info(
            "music handler: matched existing playlist %r (%d tracks)",
            name,
            len(tracks),
        )
        text = f"Playing {name} ({len(tracks)} tracks)."
        if pid:
            text = text.rstrip() + f" [MUSIC_PLAY:{pid}]"
        return {"text": text, "playlist_id": pid, "playlist_name": name}

    playlist = _ephemeral_from_library(query)
    if not playlist:
        logger.info("music handler: no match for %r", query)
        return {
            "text": "Unable to find the song in our list.",
            "playlist_id": None,
            "playlist_name": None,
        }

    name = playlist.get("name", "")
    tracks = playlist.get("tracks", []) or []
    pid = playlist.get("id")
    text = f"Playing {name} ({len(tracks)} tracks)."
    if pid:
        text = text.rstrip() + f" [MUSIC_PLAY:{pid}]"
    return {"text": text, "playlist_id": pid, "playlist_name": name}
