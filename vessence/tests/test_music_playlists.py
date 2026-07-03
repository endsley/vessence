from pathlib import Path

from jane_web.music_playlists import (
    content_words,
    extract_fallback_music_play_marker,
    find_matching_playlist,
    is_temporary_playlist_name,
    music_play_marker,
    normalize_music_query,
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
