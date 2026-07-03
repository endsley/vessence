"""Pure message helpers for qwen_query.py."""

from __future__ import annotations


LOCAL_QWEN_HEADER = "--- LOCAL QWEN RESPONSE (OLLAMA) ---"
OLLAMA_UNREACHABLE_MESSAGE = (
    "CRITICAL ERROR: Local Ollama service is UNREACHABLE. "
    "Refusing to fall back to Gemini."
)


def qwen_system_instruction(user_name: str) -> str:
    return (
        f"You are Jane, {user_name}'s technical expert and friend. "
        "You are acting as the local Qwen specialist. "
        "Provide expert technical assistance using your local knowledge."
    )


def usage_message(script_name: str = "qwen_query.py") -> str:
    return f"Usage: {script_name} <prompt>"
