"""Comprehensive audit tests for jane_web.jane_v2.classes.music_play.handler.

Covers: behavioral specs from docstring, edge cases, integration mocks,
and structural invariants on dispatch logic and return shapes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: ensure vessence root is importable
# ---------------------------------------------------------------------------

_VESSENCE = Path(__file__).resolve().parents[1]
for p in [str(_VESSENCE), str(_VESSENCE / "agent_skills")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jane_web.jane_v2.classes.music_play.handler import (  # noqa: E402
    _ephemeral_from_library,
    _format_play_response,
    _match_existing_playlist,
    _normalize,
    handle,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _playlist(pid="pl-1", name="My Chill Mix", tracks=None):
    return {
        "id": pid,
        "name": name,
        "tracks": tracks if tracks is not None else [{"title": f"Track {i}"} for i in range(5)],
    }


@pytest.fixture
def mock_vault_playlists():
    """Patch vault_web.playlists so _match_existing_playlist can run."""
    fake_list = MagicMock()
    fake_get = MagicMock()
    with patch.dict(sys.modules, {
        "vault_web": MagicMock(),
        "vault_web.playlists": MagicMock(list_playlists=fake_list, get_playlist=fake_get),
    }):
        yield fake_list, fake_get


@pytest.fixture
def mock_v1_resolver():
    """Patch the v1 library scanner used by _ephemeral_from_library."""
    with patch("jane_web.main.create_music_playlist_from_query") as m:
        yield m


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BEHAVIORAL TESTS — documented behavior from docstring
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocstringContract:
    """Docstring says:
    - resume → escalate (return None)
    - no params → escalate
    - missing kind → escalate
    - search vault first, then v1 fallback
    - returns dict with [MUSIC_PLAY:<id>] marker
    """

    def test_resume_escalates(self):
        result = handle("play something", params={"kind": "resume", "query": ""})
        assert result is None

    def test_no_params_escalates(self):
        result = handle("play music", params=None)
        assert result is None

    def test_empty_params_escalates(self):
        result = handle("play music", params={})
        assert result is None

    def test_missing_kind_escalates(self):
        result = handle("play", params={"query": "jazz"})
        assert result is None

    def test_empty_kind_escalates(self):
        result = handle("play", params={"kind": "", "query": "jazz"})
        assert result is None

    def test_whitespace_kind_escalates(self):
        result = handle("play", params={"kind": "   ", "query": "jazz"})
        assert result is None

    def test_vault_match_returned_before_v1(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist()
        fake_list.return_value = [{"id": "pl-1", "name": "My Chill Mix"}]
        fake_get.return_value = pl

        with patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library"
        ) as v1_mock:
            result = handle("play my chill mix", params={"kind": "playlist", "query": "My Chill Mix"})
            v1_mock.assert_not_called()

        assert result is not None
        assert result["playlist_id"] == "pl-1"

    def test_v1_fallback_when_no_vault_match(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        fake_list.return_value = []

        with patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library"
        ) as v1_mock:
            v1_mock.return_value = _playlist(pid="eph-1", name="Ephemeral Jazz")
            result = handle("play jazz", params={"kind": "genre", "query": "jazz"})

        assert result is not None
        assert result["playlist_id"] == "eph-1"

    def test_music_play_marker_in_text(self):
        pl = _playlist(pid="abc-123")
        result = _format_play_response(pl)
        assert "[MUSIC_PLAY:abc-123]" in result["text"]

    def test_marker_absent_when_no_id(self):
        pl = _playlist(pid=None)
        result = _format_play_response(pl)
        assert "[MUSIC_PLAY:" not in result["text"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES — empty input, malformed input, None, long input
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalize:
    def test_none_input(self):
        assert _normalize(None) == ""

    def test_empty_string(self):
        assert _normalize("") == ""

    def test_whitespace_only(self):
        assert _normalize("   ") == ""

    def test_collapses_whitespace(self):
        assert _normalize("  hello   world  ") == "hello world"

    def test_lowercases(self):
        assert _normalize("My Chill MIX") == "my chill mix"

    def test_very_long_input(self):
        long_str = "a " * 5000
        result = _normalize(long_str)
        assert len(result) > 0
        assert "  " not in result


class TestHandleEdgeCases:
    def test_none_prompt(self):
        result = handle(None, params={"kind": "song", "query": "test"})
        assert result is None or isinstance(result, dict)

    def test_empty_prompt(self):
        result = handle("", params={"kind": "song", "query": "test"})
        assert result is None or isinstance(result, dict)

    def test_params_with_none_kind(self):
        result = handle("play", params={"kind": None, "query": "jazz"})
        assert result is None

    def test_params_with_none_query(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=None,
        ):
            result = handle("play something", params={"kind": "song", "query": None})
        assert result is not None
        assert "Unable to find" in result["text"]

    def test_very_long_query(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=None,
        ):
            result = handle("play", params={"kind": "song", "query": "x" * 10000})
        assert result is not None
        assert result["playlist_id"] is None

    def test_kind_case_insensitive(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=_playlist(),
        ):
            result = handle("play", params={"kind": "SONG", "query": "test"})
        assert result is not None

    def test_kind_with_surrounding_whitespace(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=_playlist(),
        ):
            result = handle("play", params={"kind": "  song  ", "query": "test"})
        assert result is not None

    def test_resume_case_insensitive(self):
        result = handle("resume", params={"kind": "RESUME", "query": ""})
        assert result is None

    def test_resume_with_whitespace(self):
        result = handle("resume", params={"kind": "  resume  ", "query": ""})
        assert result is None

    def test_extra_params_ignored(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=_playlist(),
        ):
            result = handle("play", params={"kind": "song", "query": "test", "extra": "ignored"})
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INTEGRATION POINTS — vault playlist matching, v1 resolver
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchExistingPlaylist:
    def test_import_failure_returns_none(self):
        with patch.dict(sys.modules, {"vault_web": None, "vault_web.playlists": None}):
            assert _match_existing_playlist("test") is None

    def test_empty_query_returns_none(self, mock_vault_playlists):
        assert _match_existing_playlist("") is None
        assert _match_existing_playlist(None) is None

    def test_no_candidates_returns_none(self, mock_vault_playlists):
        fake_list, _ = mock_vault_playlists
        fake_list.return_value = []
        assert _match_existing_playlist("jazz") is None

    def test_none_candidates_returns_none(self, mock_vault_playlists):
        fake_list, _ = mock_vault_playlists
        fake_list.return_value = None
        assert _match_existing_playlist("jazz") is None

    def test_exact_match(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist()
        fake_list.return_value = [{"id": "pl-1", "name": "My Chill Mix"}]
        fake_get.return_value = pl

        result = _match_existing_playlist("my chill mix")
        assert result == pl
        fake_get.assert_called_once_with("pl-1")

    def test_exact_match_case_insensitive(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist()
        fake_list.return_value = [{"id": "pl-1", "name": "My Chill Mix"}]
        fake_get.return_value = pl

        result = _match_existing_playlist("MY CHILL MIX")
        assert result == pl

    def test_substring_match_query_in_name(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist(name="Ultimate Jazz Collection")
        fake_list.return_value = [{"id": "pl-2", "name": "Ultimate Jazz Collection"}]
        fake_get.return_value = pl

        result = _match_existing_playlist("jazz")
        assert result == pl

    def test_substring_match_name_in_query(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist(name="Jazz")
        fake_list.return_value = [{"id": "pl-3", "name": "Jazz"}]
        fake_get.return_value = pl

        result = _match_existing_playlist("play some jazz music please")
        assert result == pl

    def test_fuzzy_match_with_rapidfuzz(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        pl = _playlist(name="Chill Vibes Mix")
        fake_list.return_value = [{"id": "pl-4", "name": "Chill Vibes Mix"}]
        fake_get.return_value = pl

        with patch.dict(sys.modules, {}):
            try:
                from rapidfuzz import fuzz  # noqa: F401
                result = _match_existing_playlist("chill vibe mix")
                assert result == pl
            except ImportError:
                pytest.skip("rapidfuzz not installed")

    def test_fuzzy_below_threshold_returns_none(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        fake_list.return_value = [{"id": "pl-5", "name": "Completely Different Name"}]

        result = _match_existing_playlist("xyz abc 123")
        assert result is None

    def test_skips_empty_name_candidates(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        fake_list.return_value = [
            {"id": "pl-a", "name": ""},
            {"id": "pl-b", "name": "Jazz Favorites"},
        ]
        fake_get.return_value = _playlist(pid="pl-b", name="Jazz Favorites")

        result = _match_existing_playlist("jazz favorites")
        assert result is not None
        fake_get.assert_called_once_with("pl-b")

    def test_exact_match_beats_substring(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        fake_list.return_value = [
            {"id": "pl-sub", "name": "My Jazz Favorites Extended"},
            {"id": "pl-exact", "name": "Jazz"},
        ]
        fake_get.return_value = _playlist(pid="pl-exact", name="Jazz")

        result = _match_existing_playlist("jazz")
        assert result is not None
        fake_get.assert_called_once_with("pl-exact")


class TestEphemeralFromLibrary:
    def test_import_failure_returns_none(self):
        with patch.dict(sys.modules, {"jane_web": MagicMock(), "jane_web.main": None}):
            assert _ephemeral_from_library("test") is None

    def test_returns_playlist_from_v1(self):
        pl = _playlist(pid="eph-1", name="V1 Result")
        with patch("jane_web.main.create_music_playlist_from_query", return_value=pl):
            result = _ephemeral_from_library("some query")
        assert result == pl

    def test_passes_query_to_v1(self):
        with patch("jane_web.main.create_music_playlist_from_query", return_value=None) as m:
            _ephemeral_from_library("jazz vibes")
        m.assert_called_once_with("jazz vibes")

    def test_empty_query_passed_as_empty_string(self):
        with patch("jane_web.main.create_music_playlist_from_query", return_value=None) as m:
            _ephemeral_from_library("")
        m.assert_called_once_with("")

    def test_none_query_passed_as_empty_string(self):
        with patch("jane_web.main.create_music_playlist_from_query", return_value=None) as m:
            _ephemeral_from_library(None)
        m.assert_called_once_with("")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. _format_play_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatPlayResponse:
    def test_basic_shape(self):
        result = _format_play_response(_playlist())
        assert "text" in result
        assert "playlist_id" in result
        assert "playlist_name" in result

    def test_track_count_in_text(self):
        pl = _playlist(tracks=[{"t": 1}, {"t": 2}, {"t": 3}])
        result = _format_play_response(pl)
        assert "3 tracks" in result["text"]

    def test_name_in_text(self):
        pl = _playlist(name="Smooth Jazz")
        result = _format_play_response(pl)
        assert "Smooth Jazz" in result["text"]

    def test_marker_format(self):
        pl = _playlist(pid="test-id-42")
        result = _format_play_response(pl)
        assert "[MUSIC_PLAY:test-id-42]" in result["text"]

    def test_no_tracks_shows_zero(self):
        pl = _playlist(tracks=[])
        result = _format_play_response(pl)
        assert "0 tracks" in result["text"]

    def test_none_tracks_shows_zero(self):
        pl = {"id": "x", "name": "Empty", "tracks": None}
        result = _format_play_response(pl)
        assert "0 tracks" in result["text"]

    def test_missing_name_defaults(self):
        pl = {"id": "x", "tracks": []}
        result = _format_play_response(pl)
        assert "that playlist" in result["text"]

    def test_missing_id_no_marker(self):
        pl = {"name": "Test", "tracks": []}
        result = _format_play_response(pl)
        assert "[MUSIC_PLAY:" not in result["text"]
        assert result["playlist_id"] is None

    def test_empty_string_id_no_marker(self):
        pl = {"id": "", "name": "Test", "tracks": []}
        result = _format_play_response(pl)
        assert "[MUSIC_PLAY:" not in result["text"]

    def test_completely_empty_playlist(self):
        result = _format_play_response({})
        assert "text" in result
        assert "playlist_id" in result
        assert "playlist_name" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. handle() — full dispatch
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleDispatch:
    """Test handle() end-to-end with mocked dependencies."""

    def _patch_both(self, vault_result=None, v1_result=None):
        return (
            patch(
                "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
                return_value=vault_result,
            ),
            patch(
                "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
                return_value=v1_result,
            ),
        )

    def test_vault_hit_returns_formatted(self):
        pl = _playlist(pid="v-1", name="Vault Hit")
        p1, p2 = self._patch_both(vault_result=pl)
        with p1, p2:
            result = handle("play", params={"kind": "playlist", "query": "vault hit"})
        assert result["playlist_id"] == "v-1"
        assert "[MUSIC_PLAY:v-1]" in result["text"]

    def test_v1_hit_returns_formatted(self):
        pl = _playlist(pid="e-1", name="V1 Hit")
        p1, p2 = self._patch_both(v1_result=pl)
        with p1, p2:
            result = handle("play", params={"kind": "song", "query": "some song"})
        assert result["playlist_id"] == "e-1"

    def test_both_miss_returns_unable_text(self):
        p1, p2 = self._patch_both()
        with p1, p2:
            result = handle("play", params={"kind": "song", "query": "nonexistent"})
        assert result is not None
        assert "Unable to find" in result["text"]
        assert result["playlist_id"] is None
        assert result["playlist_name"] is None

    def test_empty_query_skips_vault_goes_to_v1(self):
        pl = _playlist(pid="e-2", name="Random")
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist"
        ) as vault_mock, patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=pl,
        ):
            result = handle("play something", params={"kind": "shuffle", "query": ""})
        vault_mock.assert_not_called()
        assert result["playlist_id"] == "e-2"

    @pytest.mark.parametrize("kind", ["shuffle", "song", "artist", "playlist", "genre", "mood"])
    def test_all_documented_kinds_dispatch(self, kind):
        pl = _playlist()
        p1, p2 = self._patch_both(v1_result=pl)
        with p1, p2:
            result = handle("play", params={"kind": kind, "query": "test"})
        assert result is not None
        assert "text" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. STRUCTURAL INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralInvariants:
    """High-leverage checks on dispatch, return shapes, and logical consistency."""

    # -- Return shape: every non-None result from handle() must have text, playlist_id, playlist_name --

    def test_success_return_shape_from_vault(self):
        pl = _playlist()
        result = _format_play_response(pl)
        assert set(result.keys()) == {"text", "playlist_id", "playlist_name"}
        assert isinstance(result["text"], str)

    def test_failure_return_shape(self):
        with patch(
            "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
            return_value=None,
        ), patch(
            "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
            return_value=None,
        ):
            result = handle("play", params={"kind": "song", "query": "nope"})
        assert set(result.keys()) == {"text", "playlist_id", "playlist_name"}
        assert result["playlist_id"] is None
        assert result["playlist_name"] is None

    def test_resume_is_only_kind_that_escalates(self):
        """Only 'resume' should return None for a valid kind. All other kinds
        should dispatch to search and return a dict."""
        pl = _playlist()
        for kind in ["shuffle", "song", "artist", "playlist", "genre", "mood"]:
            with patch(
                "jane_web.jane_v2.classes.music_play.handler._match_existing_playlist",
                return_value=None,
            ), patch(
                "jane_web.jane_v2.classes.music_play.handler._ephemeral_from_library",
                return_value=pl,
            ):
                result = handle("play", params={"kind": kind, "query": "test"})
            assert result is not None, f"kind={kind!r} unexpectedly escalated"

        result = handle("play", params={"kind": "resume", "query": ""})
        assert result is None

    # -- handle() is sync (not async) per docstring --

    def test_handle_is_sync(self):
        import asyncio
        assert not asyncio.iscoroutinefunction(handle)

    # -- Escalation conditions are exhaustive --

    def test_all_escalation_paths_return_none(self):
        assert handle("x", params=None) is None
        assert handle("x", params={}) is None
        assert handle("x", params={"kind": "resume"}) is None
        assert handle("x", params={"kind": ""}) is None
        assert handle("x", params={"kind": None}) is None
        assert handle("x", params={"query": "test"}) is None

    # -- MUSIC_PLAY marker: present iff playlist has an id --

    def test_marker_present_iff_id_exists(self):
        with_id = _format_play_response({"id": "abc", "name": "Test", "tracks": []})
        assert "[MUSIC_PLAY:abc]" in with_id["text"]

        without_id = _format_play_response({"name": "Test", "tracks": []})
        assert "[MUSIC_PLAY:" not in without_id["text"]

        empty_id = _format_play_response({"id": "", "name": "Test", "tracks": []})
        assert "[MUSIC_PLAY:" not in empty_id["text"]

        none_id = _format_play_response({"id": None, "name": "Test", "tracks": []})
        assert "[MUSIC_PLAY:" not in none_id["text"]

    # -- Playlist matching: exact match takes priority over substring --

    def test_exact_match_priority_over_substring(self, mock_vault_playlists):
        fake_list, fake_get = mock_vault_playlists
        fake_list.return_value = [
            {"id": "sub", "name": "Jazz Classics Extended"},
            {"id": "exact", "name": "Jazz Classics"},
        ]
        fake_get.return_value = _playlist(pid="exact", name="Jazz Classics")

        result = _match_existing_playlist("Jazz Classics")
        fake_get.assert_called_with("exact")

    # -- No double-space or formatting bugs in output text --

    def test_no_double_spaces_in_text(self):
        pl = _playlist(pid="x", name="Test", tracks=[{"t": 1}])
        result = _format_play_response(pl)
        assert "  " not in result["text"]

    # -- _normalize is idempotent --

    def test_normalize_idempotent(self):
        for s in ["Hello World", "  spaced  out  ", "UPPER", "", None]:
            once = _normalize(s)
            twice = _normalize(once)
            assert once == twice, f"_normalize not idempotent for {s!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Concurrency note from docstring — sync handler
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrencyContract:
    """Docstring says handle is sync on purpose — pipeline offloads to thread."""

    def test_handle_returns_directly_not_coroutine(self):
        result = handle("x", params=None)
        import asyncio
        assert not asyncio.iscoroutine(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
