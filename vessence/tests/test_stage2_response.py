from jane_web.jane_v2.stage2_response import (
    assemble_music_text,
    stage2_response_parts,
    wrap_spoken,
)


def test_assemble_music_text_appends_playlist_marker_once():
    result = {"text": "Playing that now.", "playlist_id": "abc123"}

    assert assemble_music_text(result) == "Playing that now. [MUSIC_PLAY:abc123]"
    assert assemble_music_text({"text": "Already [MUSIC_PLAY:abc123]", "playlist_id": "abc123"}) == (
        "Already [MUSIC_PLAY:abc123]"
    )


def test_wrap_spoken_leaves_client_tool_marker_outside_spoken_tag():
    text = 'Sending. [[CLIENT_TOOL:contacts.sms_send:{"draft_id":"d1"}]]'

    assert wrap_spoken(text) == (
        '<spoken>Sending.</spoken> [[CLIENT_TOOL:contacts.sms_send:{"draft_id":"d1"}]]'
    )


def test_stage2_response_parts_keeps_print_block_unspoken_and_returns_extras():
    text, extras = stage2_response_parts(
        {
            "text": "Found the playlist.",
            "print": "Track list",
            "playlist_id": "pl-1",
            "playlist_name": "Focus",
            "client_tools": [{"name": "tool", "args": {"x": 1}}],
            "conversation_end": True,
        }
    )

    assert text == "<spoken>Found the playlist.</spoken> [MUSIC_PLAY:pl-1]\n\nTrack list"
    assert extras == {
        "playlist_id": "pl-1",
        "playlist_name": "Focus",
        "client_tools": [{"name": "tool", "args": {"x": 1}}],
        "conversation_end": True,
    }
