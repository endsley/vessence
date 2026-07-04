from pathlib import Path

from jane_web.music_playlists import (
    cleanup_temporary_playlists,
    content_words,
    existing_playlist_for_music_query,
    extract_fallback_music_play_marker,
    find_matching_playlist,
    is_temporary_playlist_name,
    music_playlist_from_query,
    music_playlist_delegate_context,
    music_playlist_delegate_error_context,
    music_playlist_no_match_delegate_context,
    music_playlist_no_match_task_context,
    music_playlist_task_context,
    music_playlist_task_error_context,
    music_play_marker,
    normalize_music_query,
    playlist_track_names,
    playlist_name_for_query,
    playlist_tracks,
    real_user_playlists,
    replace_music_play_marker,
    select_music_files,
    should_delete_temporary_playlist,
)


def test_normalize_music_query_strips_voice_wrappers_and_detects_random():
    parts = normalize_music_query("Play my Coldplay playlist")

    assert parts.q == "play my coldplay playlist"
    assert parts.q_norm == "play my coldplay playlist"
    assert parts.q_core == "coldplay"
    assert not parts.is_random

    random_parts = normalize_music_query("Some Music")
    assert random_parts.is_random
    assert playlist_name_for_query(random_parts) == "Random Mix"


def test_temporary_playlist_helpers_use_existing_name_and_cutoff_rules():
    assert is_temporary_playlist_name("Random Mix")
    assert is_temporary_playlist_name("Playing: Coldplay")
    assert not is_temporary_playlist_name("Coldplay")
    assert should_delete_temporary_playlist(
        {"name": "Playing: Old", "created_at": "2026-07-02 12:00:00"},
        "2026-07-02 12:05:00",
    )
    assert not should_delete_temporary_playlist(
        {"name": "Coldplay", "created_at": "2026-07-02 12:00:00"},
        "2026-07-02 12:05:00",
    )


def test_music_play_marker_helpers_find_only_non_playlist_id_markers():
    assert music_play_marker("abc123") == "[MUSIC_PLAY:abc123]"
    assert extract_fallback_music_play_marker("Playing [MUSIC_PLAY:0123456789abcdef]") is None
    assert extract_fallback_music_play_marker("No marker") is None

    marker = extract_fallback_music_play_marker("Playing [MUSIC_PLAY: Coldplay ] now")

    assert marker is not None
    assert marker.marker == "[MUSIC_PLAY: Coldplay ]"
    assert marker.query == "Coldplay"
    assert replace_music_play_marker("Playing [MUSIC_PLAY: Coldplay ] now", marker, "abc123") == (
        "Playing [MUSIC_PLAY:abc123] now"
    )


def test_music_playlist_context_helpers_preserve_task_and_delegate_text():
    playlist = {
        "id": "pl-1",
        "name": "Focus",
        "tracks": [
            {"title": f"Track {index}", "path": f"Music/t{index}.mp3"}
            for index in range(12)
        ],
    }

    assert playlist_track_names(playlist) == ", ".join(f"Track {index}" for index in range(10))
    assert music_playlist_task_context(playlist) == (
        "[MUSIC DATA]\n"
        "Playlist ID: pl-1\n"
        "Name: Focus\n"
        "Tracks (12): Track 0, Track 1, Track 2, Track 3, Track 4, Track 5, Track 6, Track 7, Track 8, Track 9\n"
        "[END MUSIC DATA]"
    )
    assert music_playlist_delegate_context(playlist) == (
        "\n\n[MUSIC DATA \u2014 playlist created server-side]\n"
        "Playlist ID: pl-1\n"
        "Name: Focus\n"
        "Tracks (12): Track 0, Track 1, Track 2, Track 3, Track 4, Track 5, Track 6, Track 7, Track 8, Track 9\n"
        "[END MUSIC DATA]\n\n"
        "To play this playlist, include [MUSIC_PLAY:pl-1] in your response.\n"
        "Tell the user what you're playing. If tracks include duplicates or "
        "unwanted versions (e.g., tutorials vs originals), mention it."
    )


def test_music_playlist_context_helpers_preserve_empty_and_error_text():
    error = RuntimeError("library offline")

    assert music_playlist_no_match_task_context() == (
        "[MUSIC DATA]\nNo matching tracks found.\n[END MUSIC DATA]"
    )
    assert music_playlist_no_match_delegate_context() == (
        "\n\n[MUSIC DATA]\n"
        "No matching tracks found for this query.\n"
        "[END MUSIC DATA]\n"
        "Tell the user you couldn't find matching music."
    )
    assert music_playlist_task_error_context(error) == (
        "[MUSIC ERROR]\nlibrary offline\n[END MUSIC ERROR]"
    )
    assert music_playlist_delegate_error_context(error) == (
        "\n\n[MUSIC ERROR]\n"
        "Failed to search music library: library offline\n"
        "[END MUSIC ERROR]"
    )


def test_find_matching_playlist_ignores_temporary_and_uses_exact_substring_and_fuzzy():
    playlists = real_user_playlists(
        [
            {"id": "tmp", "name": "Playing: Coldplay"},
            {"id": "exact", "name": "Coldplay"},
            {"id": "other", "name": "Jazz Night"},
        ]
    )

    assert find_matching_playlist("coldplay", playlists)["id"] == "exact"
    assert find_matching_playlist("jazz", playlists)["id"] == "other"
    assert find_matching_playlist(
        "colplay",
        playlists,
        scorer=lambda left, right: 90 if right == "coldplay" else 0,
    )["id"] == "exact"


def test_select_music_files_uses_substring_and_then_content_word_tiers():
    files = [
        "/vault/Music/Coldplay/A Sky Full Of Stars.mp3",
        "/vault/Music/Foo Fighters/Foo Fighters Everlong.mp3",
        "/vault/Music/Foo Fighters/Foo Fighters My Hero.mp3",
    ]

    assert select_music_files("everlong", files) == ["/vault/Music/Foo Fighters/Foo Fighters Everlong.mp3"]
    assert select_music_files("songs by foo fighters", files) == [
        "/vault/Music/Foo Fighters/Foo Fighters Everlong.mp3",
        "/vault/Music/Foo Fighters/Foo Fighters My Hero.mp3",
    ]
    assert content_words("songs by foo fighters") == ["foo", "fighters"]


def test_select_music_files_uses_fuzzy_fallback_and_track_shape():
    files = [
        "/vault/Music/Coldplay/A Sky Full Of Stars.mp3",
        "/vault/Music/Foo Fighters/Everlong.mp3",
    ]

    selected = select_music_files(
        "skyfall of stars",
        files,
        scorer=lambda query, filename: 80 if "sky full" in filename else 0,
    )

    assert selected == ["/vault/Music/Coldplay/A Sky Full Of Stars.mp3"]
    assert playlist_name_for_query(normalize_music_query("coldplay")) == "Playing: Coldplay"
    assert playlist_tracks(selected, vault_parent=Path("/vault")) == [
        {"path": "Music/Coldplay/A Sky Full Of Stars.mp3", "title": "A Sky Full Of Stars"}
    ]


def test_cleanup_temporary_playlists_deletes_only_expired_generated_lists():
    from datetime import datetime

    deleted = []

    cleanup_temporary_playlists(
        list_playlists_fn=lambda: [
            {"id": "old", "name": "Playing: Old", "created_at": "2026-07-03 12:00:00"},
            {"id": "fresh", "name": "Random Mix", "created_at": "2026-07-03 12:08:00"},
            {"id": "real", "name": "Coldplay", "created_at": "2026-07-03 11:00:00"},
        ],
        delete_playlist_fn=deleted.append,
        now_fn=lambda: datetime(2026, 7, 3, 12, 10, 0),
    )

    assert deleted == ["old"]


def test_existing_playlist_for_music_query_returns_full_real_playlist_and_marks_not_temporary():
    playlist = {"id": "coldplay", "name": "Coldplay", "tracks": [{"path": "Music/coldplay.mp3"}]}
    logs = []

    class Logger:
        def info(self, *args):
            logs.append(args)

    result = existing_playlist_for_music_query(
        normalize_music_query("play my coldplay playlist"),
        original_query="play my coldplay playlist",
        list_playlists_fn=lambda: [
            {"id": "tmp", "name": "Playing: Coldplay"},
            {"id": "coldplay", "name": "Coldplay"},
        ],
        get_playlist_fn=lambda playlist_id: playlist.copy(),
        logger=Logger(),
    )

    assert result == {
        "id": "coldplay",
        "name": "Coldplay",
        "tracks": [{"path": "Music/coldplay.mp3"}],
        "temporary": False,
    }
    assert logs


def test_existing_playlist_for_music_query_skips_random_and_tolerates_list_errors():
    assert existing_playlist_for_music_query(
        normalize_music_query("some music"),
        original_query="some music",
        list_playlists_fn=lambda: (_ for _ in ()).throw(AssertionError("should skip")),
        get_playlist_fn=lambda playlist_id: {},
    ) is None
    assert existing_playlist_for_music_query(
        normalize_music_query("coldplay"),
        original_query="coldplay",
        list_playlists_fn=lambda: (_ for _ in ()).throw(RuntimeError("offline")),
        get_playlist_fn=lambda playlist_id: {"id": playlist_id},
    ) is None


def test_music_playlist_from_query_returns_existing_user_playlist():
    playlist = {"id": "coldplay", "name": "Coldplay", "tracks": [{"path": "Music/coldplay.mp3"}]}

    result = music_playlist_from_query(
        "play my coldplay playlist",
        list_playlists_fn=lambda: [{"id": "coldplay", "name": "Coldplay"}],
        get_playlist_fn=lambda playlist_id: playlist.copy(),
        create_playlist_fn=lambda name, tracks: {"id": "new", "name": name, "tracks": tracks},
        delete_playlist_fn=lambda playlist_id: None,
        vault_home="/vault",
        glob_files_fn=lambda pattern, recursive: [],
        random_sample_fn=lambda files, count: files[:count],
    )

    assert result == {
        "id": "coldplay",
        "name": "Coldplay",
        "tracks": [{"path": "Music/coldplay.mp3"}],
        "temporary": False,
    }


def test_music_playlist_from_query_creates_temporary_playlist_from_selected_files():
    created = []
    files = [
        "/vault/Music/Foo Fighters/Everlong.mp3",
        "/vault/Music/Coldplay/A Sky Full Of Stars.mp3",
    ]

    def create_playlist(name, tracks):
        created.append((name, tracks))
        return {"id": "new", "name": name, "tracks": tracks}

    result = music_playlist_from_query(
        "everlong",
        list_playlists_fn=lambda: [],
        get_playlist_fn=lambda playlist_id: None,
        create_playlist_fn=create_playlist,
        delete_playlist_fn=lambda playlist_id: None,
        vault_home="/vault",
        glob_files_fn=lambda pattern, recursive: files,
        random_sample_fn=lambda items, count: items[:count],
    )

    assert created == [
        ("Playing: Everlong", [{"path": "Music/Foo Fighters/Everlong.mp3", "title": "Everlong"}])
    ]
    assert result == {
        "id": "new",
        "name": "Playing: Everlong",
        "tracks": [{"path": "Music/Foo Fighters/Everlong.mp3", "title": "Everlong"}],
        "temporary": True,
    }
