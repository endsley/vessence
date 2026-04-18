"""MUSIC_PLAY — play/queue music commands."""

CLASS_NAME = "MUSIC_PLAY"
NEEDS_LLM = True

EXAMPLES = [
    "play shakira", "play some jazz", "play taylor swift",
    "play something upbeat", "play my workout playlist",
    "put on some music", "put on the beatles",
    "shuffle my playlist", "shuffle some rock",
    "throw on some hip hop", "throw on drake",
    "play me something relaxing", "can you play classical music",
    "play billie eilish", "play bruno mars",
    "can you play some jazz for me", "i want to listen to coldplay",
    "listen to some country music", "listen to the weekend",
    "play lo-fi hip hop", "play some background music",
    "put on some chill music", "put on a playlist",
    "shuffle some songs", "play something fun",
    "can you throw on some music", "turn on some music",
    "start playing music", "play some 80s hits",
    "play old school hip hop", "play some classical",
    "play something for studying", "queue up some songs",
    "put on eminem", "play some rock",
    "can I hear some reggae", "play some salsa",
    "play queen", "play led zeppelin",
    "throw on some EDM", "put on some pop music",
    "shuffle everything", "play a random song",
    "play the top hits", "play some R&B",
    "put on some smooth jazz", "play frank sinatra",
    "throw on some country", "play some blues",
    "play spotify", "put on some k-pop",
    # Descriptive / full-title song requests
    "can you play sky full of stars", "play sky full of stars",
    "play a sky full of stars", "play the song sky full of stars",
    "can you play the song called sky full of stars",
    "play a song called stay with me", "play the song about love",
    "can you play something by coldplay", "play any coldplay song",
    "play the song with the stars in the title",
    "can you play a relaxing song", "play an upbeat song for me",
    "can you play something mellow", "play a feel good song",
    "play that song I like", "play something chill for me",
    # Ambient / sleep / nature sounds
    "I want to listen to sleep sounds", "play sleep sounds",
    "play some white noise", "play ambient sounds",
    "play rain sounds", "play ocean sounds",
    "put on some sleep music", "play something to fall asleep to",
    # Playback controls — always tied to music/song/track vocabulary so
    # they don't poach workouts, videos, lists, etc. Bare "turn it up" /
    # "louder" are NOT added here because they ambiguously apply to any
    # audio source; the v3 classifier's FIFO context handles those.
    "skip this song", "skip this track", "skip to the next song",
    "skip to the next track", "next song", "next track",
    "play the next song", "go to the next song",
    "previous song", "go back a song", "play the previous track",
    "stop the music", "stop the song", "pause the music",
    "pause the song", "resume the music",
    "turn the music up", "turn the volume of the music up",
    "turn the music down", "turn the volume of the music down",
    "make the music louder", "make the music quieter",
]

CONTEXT = """\
The user wants to play music.
Output exactly:
CLASSIFICATION: MUSIC_PLAY
QUERY: <artist, song, or genre — nothing else>

Example:
User: play bohemian rhapsody by queen
CLASSIFICATION: MUSIC_PLAY
QUERY: bohemian rhapsody queen"""
