# Model Context Protocol (MCP) Specification

Every tool and essence in Vessence MUST define an MCP before it is considered complete. The MCP is how Jane knows what a tool can do and how to use it. Without a complete MCP, the tool cannot be invoked by Jane and should not be shipped.

## MCP File Location

Each tool/essence defines its MCP in:
```
<tool_or_essence_dir>/mcp.json
```

## Required Fields

```json
{
  "name": "Music Playlist",
  "version": "1.0",
  
  "triggers": {
    "keywords": ["play", "music", "song", "playlist", "artist"],
    "phrases": ["play a song", "play music", "play me something", "shuffle my playlist"],
    "description": "Activates when user wants to play, search, or manage music from their vault."
  },

  "commands": [
    {
      "name": "play_search",
      "description": "Search vault music by keyword and play matching tracks",
      "parameters": {
        "query": {
          "type": "string",
          "required": true,
          "description": "Search term: artist name, song title, or 'random'"
        }
      },
      "action": "POST /api/music/play",
      "response_tag": "[MUSIC_PLAY:{playlist_id}]",
      "example_input": "play the scientist",
      "example_response": "Playing 'Coldplay - The Scientist' for you. [MUSIC_PLAY:abc123]"
    },
    {
      "name": "list_playlists",
      "description": "Show saved playlists",
      "parameters": {},
      "action": "GET /api/playlists",
      "response_tag": null,
      "example_input": "show my playlists",
      "example_response": "You have 3 playlists: Chill Vibes (12 songs), Workout (8 songs), Favorites (25 songs)."
    }
  ],

  "response_format": {
    "tags": {
      "[MUSIC_PLAY:{playlist_id}]": "Android navigates to Music Player and starts playing the playlist",
      "[MUSIC_STOP]": "Android stops current playback"
    },
    "display": "Response text is shown in chat bubble. Tags are stripped from display and parsed by the client.",
    "tts": "Response text (without tags) is spoken by TTS if voice mode is active."
  },

  "error_handling": {
    "no_results": "Tell user no matching songs were found. Suggest alternatives.",
    "service_unavailable": "Tell user the music service is temporarily unavailable.",
    "fallback": "If the tool cannot handle the request, delegate to Claude with DELEGATE_OPUS."
  },

  "permissions": ["file_system"],
  
  "client_requirements": {
    "android": "ExoPlayer for audio playback. Music screen with playlist view.",
    "web": "HTML5 Audio element for playback."
  }
}
```

## How Jane Uses the MCP

### At Startup
1. Jane loads all `mcp.json` files from installed tools/essences
2. Builds a keyword index: `"play" → Music Playlist`, `"weather" → Weather`, etc.
3. Stores the command definitions for prompt context injection

### Per Request
1. User says "play the scientist"
2. Gemma4 router checks keyword index → matches "play" → loads Music Playlist MCP
3. MCP is injected into gemma4's system prompt as context
4. Gemma4 knows the exact command format, parameters, and response tags
5. Gemma4 responds: "Playing 'The Scientist' for you. [MUSIC_PLAY:abc123]"
6. Android parses `[MUSIC_PLAY:abc123]` → navigates to music player → starts playback

### For Claude (DELEGATE path)
1. If gemma4 delegates, the MCP is included in Claude's context too
2. Claude calls the tool's API endpoint directly
3. Claude formats the response with the correct tags

## MCP for Built-in Capabilities

Even built-in features should have MCPs:

### Weather
```json
{
  "name": "Weather",
  "triggers": {"keywords": ["weather", "temperature", "rain", "forecast", "umbrella"]},
  "commands": [{"name": "current_weather", "action": "READ $VESSENCE_DATA_HOME/cache/weather.json"}],
  "response_format": {"display": "Include current temp, high/low, condition, AQI"}
}
```

### File Management (Life Librarian)
```json
{
  "name": "Life Librarian",
  "triggers": {"keywords": ["file", "document", "photo", "upload", "vault"]},
  "commands": [{"name": "search_files", "action": "GET /api/files/search?q={query}"}]
}
```

## Marketplace Requirements

For essences sold on the marketplace:
1. MCP is **mandatory** — rejected without it
2. MCP is shown to buyers as the "capabilities list"
3. MCP is validated during AI quality testing
4. MCP examples are used to test the essence actually works

## Builder Interview — MCP Phase (Mandatory)

When a user asks Jane to build a tool or essence, Jane MUST guide them through the MCP definition before writing any code. This is a 3-step interview:

### Step 1: Purpose
Jane asks:
- "What does this tool do?"
- "Who is it for?"
- "What problem does it solve?"

Jane summarizes and confirms before proceeding.

### Step 2: Key Capabilities
Jane asks:
- "List every action this tool can perform."
- "For each action, give me a one-sentence description."

Jane presents the capability list and confirms before proceeding.

### Step 3: MCP Definition
For EACH capability, Jane asks:
1. "What words or phrases would a user say to trigger this?" → `triggers`
2. "What information does it need from the user?" → `parameters`
3. "What does it actually do?" → `action` (API endpoint, file read, navigation)
4. "What should the response look like?" → `response_tag` and display format
5. "What happens if it fails?" → `error_handling`

Jane generates the `mcp.json` from the answers and presents it for approval.

**Jane does NOT proceed to code generation until the MCP is fully defined and the user approves it.**

## Completeness Checklist

Before shipping any tool/essence, verify:
- [ ] `mcp.json` exists and is valid JSON
- [ ] All trigger keywords are defined
- [ ] All commands have parameters, action, and response_tag
- [ ] Error handling is defined
- [ ] At least one example_input/example_response per command
- [ ] Client requirements are documented
- [ ] Jane can invoke the tool from a voice or text prompt using only the MCP
