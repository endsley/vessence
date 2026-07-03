from jane_web.jane_v2.classes.music_play import handler
from jane_web.jane_v2.classes.music_play.matching import (
    ACTIONABLE_KINDS,
    FUZZY_MATCH_THRESHOLD,
    format_play_response,
    normalize,
    select_playlist_candidate,
)


def _playlists() -> list[dict]:
    return [
        {"id": "p1", "name": "Morning Focus"},
        {"id": "p2", "name": "Kitchen Dance Mix"},
        {"id": "p3", "name": "Deep Work Instrumentals"},
    ]


def test_handler_uses_extracted_music_matching_helpers() -> None:
    assert handler._ACTIONABLE_KINDS is ACTIONABLE_KINDS
    assert handler._normalize is normalize
    assert handler._select_playlist_candidate is select_playlist_candidate
    assert handler._format_play_response is format_play_response


def test_normalize_collapses_case_and_spacing() -> None:
    assert normalize("  Morning   Focus ") == "morning focus"


def test_select_playlist_candidate_prefers_exact_then_substring_matches() -> None:
    playlists = _playlists()

    assert select_playlist_candidate("morning focus", playlists) is playlists[0]
    assert select_playlist_candidate("dance", playlists) is playlists[1]
    assert select_playlist_candidate("deep work instrumentals playlist", playlists) is playlists[2]
    assert select_playlist_candidate("", playlists) is None
    assert select_playlist_candidate("missing", []) is None


def test_select_playlist_candidate_uses_optional_fuzzy_scorer() -> None:
    playlists = _playlists()

    def score(query: str, name: str) -> int:
        if query == "deep wrk instr" and name == "deep work instrumentals":
            return FUZZY_MATCH_THRESHOLD
        return 10

    assert select_playlist_candidate("deep wrk instr", playlists, score_func=score) is playlists[2]
    assert select_playlist_candidate("deep wrk instr", playlists, score_func=lambda _q, _n: 79) is None


def test_format_play_response_includes_marker_when_playlist_has_id() -> None:
    assert format_play_response({"id": "p1", "name": "Morning Focus", "tracks": ["a", "b"]}) == {
        "text": "Playing Morning Focus (2 tracks). [MUSIC_PLAY:p1]",
        "playlist_id": "p1",
        "playlist_name": "Morning Focus",
    }
    assert format_play_response({"name": "Loose Tracks", "tracks": []}) == {
        "text": "Playing Loose Tracks (0 tracks).",
        "playlist_id": None,
        "playlist_name": "Loose Tracks",
    }
