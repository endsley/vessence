from memory.v1 import janitor_memory
from memory.v1.janitor_code_verification import (
    code_verification_prompt,
    frontier_fix_prompt,
    is_code_memory,
)


def _memory():
    return {
        "id": "abcdef1234567890",
        "topic": "Project: vessence",
        "text": "The jane_web pipeline uses qwen for Stage 2.",
    }


def test_janitor_memory_uses_extracted_code_memory_detector():
    assert janitor_memory._is_code_memory is is_code_memory
    assert is_code_memory("The handler lives in jane_web/main.py")
    assert is_code_memory("Ollama keep_alive changed")
    assert not is_code_memory("Chieh likes tea")


def test_code_verification_prompt_preserves_codex_contract():
    prompt = code_verification_prompt(_memory())

    assert prompt.startswith("You are auditing ONE ChromaDB memory")
    assert "MEMORY (id=abcdef123456, topic=Project: vessence):" in prompt
    assert "The jane_web pipeline uses qwen for Stage 2." in prompt
    assert '"verdict": "ACCURATE|STALE|PARTIAL"' in prompt
    assert "no markdown fences" in prompt


def test_frontier_fix_prompt_preserves_frontier_contract():
    prompt = frontier_fix_prompt(
        _memory(),
        {
            "verdict": "STALE",
            "explanation": "Stage 2 changed",
            "corrected_text": "Corrected memory",
        },
    )

    assert prompt.startswith("Codex flagged this ChromaDB memory")
    assert "CODEX VERDICT: STALE" in prompt
    assert "CODEX EXPLANATION: Stage 2 changed" in prompt
    assert "CODEX SUGGESTED CORRECTION: Corrected memory" in prompt
    assert '"action": "update|delete|keep"' in prompt
