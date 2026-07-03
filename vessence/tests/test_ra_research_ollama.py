from agent_skills import ra_research_cron
from agent_skills.ra_research_ollama import normalize_ollama_base_url, ollama_chat_payload


def test_ra_research_cron_uses_ollama_helpers():
    assert ra_research_cron._normalize_ollama_base_url is normalize_ollama_base_url
    assert ra_research_cron._ollama_chat_payload is ollama_chat_payload


def test_normalize_ollama_base_url_strips_trailing_slash_and_api_paths():
    assert normalize_ollama_base_url("http://localhost:11434/") == "http://localhost:11434"
    assert normalize_ollama_base_url("http://host/api/chat") == "http://host"
    assert normalize_ollama_base_url("http://host/api/generate") == "http://host"


def test_ollama_chat_payload_preserves_request_shape():
    assert ollama_chat_payload(
        "gemma",
        "system",
        "user",
        num_ctx=4096,
    ) == {
        "model": "gemma",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": 4096, "temperature": 0.1},
    }


def test_ollama_chat_payload_allows_temperature_override():
    assert ollama_chat_payload(
        "gemma",
        "system",
        "user",
        num_ctx=4096,
        temperature=0.2,
    )["options"] == {"num_ctx": 4096, "temperature": 0.2}
