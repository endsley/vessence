"""Stage 2 handler for GET_TIME — delegates to the phone's local clock."""


def handle(prompt: str) -> dict:
    return {
        "text": "",
        "client_tools": [{"name": "device.speak_time", "args": {}}],
    }
