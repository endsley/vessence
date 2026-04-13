"""Stage 2 handler for GET_TIME — delegates to the phone's local clock."""


def handle(prompt: str) -> dict:
    # Android speaks the actual time via the client tool below.
    # The text shows in the chat bubble — keep it short so the bubble
    # isn't empty while the device speaks the time aloud.
    return {
        "text": "Let me check your phone's clock.",
        "client_tools": [{"name": "device.speak_time", "args": {}}],
    }
