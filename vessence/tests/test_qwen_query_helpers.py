from agent_skills import qwen_query
from agent_skills.qwen_query_helpers import (
    LOCAL_QWEN_HEADER,
    OLLAMA_UNREACHABLE_MESSAGE,
    qwen_system_instruction,
    usage_message,
)


def test_qwen_query_uses_extracted_message_helpers():
    assert qwen_query.LOCAL_QWEN_HEADER == LOCAL_QWEN_HEADER
    assert qwen_query.OLLAMA_UNREACHABLE_MESSAGE == OLLAMA_UNREACHABLE_MESSAGE
    assert qwen_query._qwen_system_instruction is qwen_system_instruction
    assert qwen_query._usage_message is usage_message


def test_qwen_system_instruction_preserves_identity_text():
    assert qwen_system_instruction("Chieh") == (
        "You are Jane, Chieh's technical expert and friend. "
        "You are acting as the local Qwen specialist. "
        "Provide expert technical assistance using your local knowledge."
    )


def test_usage_and_error_messages_preserve_cli_text():
    assert usage_message() == "Usage: qwen_query.py <prompt>"
    assert usage_message("script.py") == "Usage: script.py <prompt>"
    assert OLLAMA_UNREACHABLE_MESSAGE == (
        "CRITICAL ERROR: Local Ollama service is UNREACHABLE. "
        "Refusing to fall back to Gemini."
    )
    assert LOCAL_QWEN_HEADER == "--- LOCAL QWEN RESPONSE (OLLAMA) ---"
