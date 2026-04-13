"""Music play class — classifier metadata."""

METADATA = {
    "name": "music play",
    "priority": 10,
    "description": (
        "[music play]\n"
        "This class handles requests to START PLAYING music from the user's "
        "local library. The library contains audio files organized into "
        "folders (each folder is effectively a natural playlist), plus a "
        "song registry that maps titles, artists, and nicknames to files.\n"
        "- Pick this class ONLY when the user wants music to actually start "
        "playing (playback action).\n"
        "- If the user asks to play/listen to/hear a song, artist, genre, "
        "sound, or playlist, classify it as music play with High confidence "
        "even if you are not sure the item exists in the library. Stage 2 "
        "will resolve the library match or report that nothing was found.\n"
        "- Example intents that belong here: play a specific song, play a "
        "playlist or folder, put on some music, shuffle a set, resume playback.\n"
        "- DOES NOT handle: questions ABOUT songs or playlists (how many "
        "songs, when was it added, who is the artist). Those go to 'others'.\n"
        "- DOES NOT handle: questions about music outside the user's library "
        "(Billboard, Spotify, lyrics, release dates). Those go to 'others'."
    ),
    "few_shot": [
        ("Play Bohemian Rhapsody", "music play:High"),
        ("Play the Scientist", "music play:High"),
        ("Play Clocks", "music play:High"),
        ("Play Yesterday", "music play:High"),
        ("Can you play some Shakira", "music play:High"),
        ("Can you played some Shakira song", "music play:High"),
        ("Can you play the song Skyfall Stars", "music play:High"),
        ("Put on some music", "music play:High"),
        ("Play my chill playlist", "music play:High"),
        ("I want to listen to something relaxing", "music play:High"),
        ("I want to listen to sleep sounds", "music play:High"),
    ],
    "ack": "Finding that now…",
    "escalate_ack": "Let me think about that music request…",
    # Injected into the Stage 3 user-message prefix when we escalate from
    # this class (e.g. classifier said music play but Stage 2 declined).
    # Gives Opus instant "I know where to look" knowledge so it doesn't
    # have to grep around on every music-related fallback.
    "escalation_context": (
        "[music data locations]\n"
        "- User playlists are stored in the vault_web SQLite database: tables "
        "`playlists` (id, name, created_at, updated_at) and `playlist_tracks` "
        "(id, playlist_id, path, position, title).\n"
        "- Python API: `from vault_web.playlists import list_playlists, "
        "get_playlist, create_playlist, update_playlist, delete_playlist`.\n"
        "- The user's music library is on disk at $VAULT_HOME/Music/, "
        "organized into folders (each folder is effectively a natural "
        "playlist). Files are .mp3.\n"
        "- To play a playlist, embed `[MUSIC_PLAY:<playlist_id>]` in your "
        "response — the Android client will pick it up and start playback.\n"
        "- Temporary playlists are auto-named 'Random Mix' or 'Playing: "
        "<query>' and get cleaned up every few minutes; user-named "
        "playlists (like 'coldplay') are permanent."
    ),
}
