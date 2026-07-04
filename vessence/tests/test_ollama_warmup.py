from jane_web.ollama_warmup import (
    heartbeat_poll_seconds,
    local_llm_prewarm_payload,
    ollama_generate_endpoint,
    ollama_heartbeat_payload,
    should_skip_heartbeat,
)


def test_ollama_generate_endpoint_normalizes_base_url() -> None:
    assert ollama_generate_endpoint("http://ollama:11434/") == "http://ollama:11434/api/generate"
    assert ollama_generate_endpoint("") == "http://localhost:11434/api/generate"


def test_local_llm_prewarm_payload_preserves_request_shape() -> None:
    assert local_llm_prewarm_payload("qwen2.5:7b", 8192, -1) == {
        "model": "qwen2.5:7b",
        "prompt": "hi",
        "stream": False,
        "options": {"num_ctx": 8192},
        "keep_alive": -1,
    }


def test_ollama_heartbeat_payload_preserves_request_shape() -> None:
    assert ollama_heartbeat_payload("qwen2.5:7b", 8192, -1) == {
        "model": "qwen2.5:7b",
        "prompt": ".",
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1,
            "num_ctx": 8192,
        },
        "keep_alive": -1,
    }


def test_heartbeat_poll_seconds_checks_more_often_than_ping_interval() -> None:
    assert heartbeat_poll_seconds(15) == 3
    assert heartbeat_poll_seconds(5) == 2
    assert heartbeat_poll_seconds(1) == 2


def test_should_skip_heartbeat_only_before_interval_elapsed() -> None:
    assert should_skip_heartbeat(14.9, 15) is True
    assert should_skip_heartbeat(15, 15) is False
    assert should_skip_heartbeat(16, 15) is False
