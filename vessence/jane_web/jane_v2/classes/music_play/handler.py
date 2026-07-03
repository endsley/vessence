"""Music play Stage 2 handler — params-driven.

Stage 1 (qwen extraction) supplies `kind` and `query` per the
PARAMS_SCHEMA in metadata.py. This handler dispatches:

  - resume → escalate (no client-side resume marker exists yet)
  - shuffle/song/artist/playlist/genre/mood → search the vault, then
    fall through to the v1 library scanner

Returns a dict the pipeline merges into its response, with a
`[MUSIC_PLAY:<id>]` marker so Android and the web UI auto-start
playback without any new fields.
"""

from __future__ import annotations

import logging
from .matching import (
    ACTIONABLE_KINDS as _ACTIONABLE_KINDS,
    format_play_response as _format_play_response,
    normalize as _normalize,
    select_playlist_candidate as _select_playlist_candidate,
)

logger = logging.getLogger(__name__)


def _match_existing_playlist(query: str) -> dict | None:
    """Return a playlist dict if the query matches an existing user playlist."""
    try:
        from vault_web.playlists import list_playlists, get_playlist
    except Exception as e:
        logger.warning("music handler: vault_web.playlists import failed: %s", e)
        return None

    candidates = list_playlists()
    if not candidates:
        return None

    score_func = None
    try:
        from rapidfuzz import fuzz
        score_func = fuzz.token_set_ratio
    except ImportError:
        pass

    match = _select_playlist_candidate(query, candidates, score_func=score_func)
    return get_playlist(match["id"]) if match else None


def _ephemeral_from_library(query: str) -> dict | None:
    try:
        from jane_web.main import create_music_playlist_from_query
    except Exception as e:
        logger.warning("music handler: could not import v1 resolver: %s", e)
        return None
    return create_music_playlist_from_query(query or "")


def handle(prompt: str, params: dict | None = None) -> dict | None:
    """Resolve a music-play request from classifier-extracted params.

    Sync on purpose — the pipeline offloads this to a thread because the
    underlying playlist resolver does DB and filesystem work.
    """
    if not params:
        logger.info("music handler: no params — escalating")
        return None

    kind = (params.get("kind") or "").strip().lower()
    query = (params.get("query") or "").strip()

    if kind == "resume":
        logger.info("music handler: resume request — escalating (no resume marker yet)")
        return None

    if not kind:
        logger.info("music handler: missing kind — escalating")
        return None

    if kind not in _ACTIONABLE_KINDS:
        logger.info("music handler: unknown kind=%r — escalating", kind)
        return None

    logger.info("music handler: kind=%r query=%r", kind, query)

    if query:
        existing = _match_existing_playlist(query)
        if existing:
            logger.info(
                "music handler: matched existing playlist %r",
                existing.get("name"),
            )
            return _format_play_response(existing)

    playlist = _ephemeral_from_library(query)
    if not playlist:
        logger.info("music handler: no match for kind=%r query=%r", kind, query)
        return {
            "text": "Unable to find the song in our list.",
            "playlist_id": None,
            "playlist_name": None,
        }

    return _format_play_response(playlist)
