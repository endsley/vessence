# Job #5: Basic Music Playback via Jane

Priority: 2
Status: partial (server endpoint done, Android detection done, navigation pending)
Created: 2026-04-03

## Description
When user says "play a song" or "play music", Jane picks a random mp3 from the vault's Music folder and streams it to the phone.

### Components:
1. **Server endpoint**: `GET /api/music/random` — returns a random mp3 stream from `$VAULT_HOME/Music/`
2. **Server endpoint**: `GET /api/music/play/{path}` — streams a specific mp3 by vault path
3. **Android**: ChatViewModel receives a `music_play` event → uses MediaPlayer to stream from server
4. **Gemma router**: detect "play song/music" keywords → SELF_HANDLE with `[MUSIC_PLAY]` tag → Android parses and plays
5. **Claude**: can also respond with `[MUSIC_PLAY:filename]` tag for specific song requests

### User's music:
- 229 mp3 files in `$VAULT_HOME/Music/Random songs/`
- Artists: Coldplay, Taylor Swift, Ed Sheeran, U2, Sara Bareilles, Shakira, etc.

### Flow:
1. User: "play a song"
2. Gemma/Claude: "Playing a random song for you." + `[MUSIC_PLAY:random]`
3. Android: detects tag, calls `/api/music/random`, starts MediaPlayer
4. Music plays in background, user can continue chatting

### Future:
- "play Coldplay" → filter by artist
- "play my playlist" → use saved playlists from Music Playlist essence
- Skip/pause/next via voice commands
