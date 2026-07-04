from jane_web import reverse_proxy
from jane_web.reverse_proxy_helpers import (
    filtered_proxy_headers,
    forwarded_request_headers,
    is_streaming_response,
    is_websocket_upgrade,
    proxy_status_payload,
    restored_upstream_port,
)


def test_reverse_proxy_uses_extracted_header_helpers():
    assert reverse_proxy._filtered_proxy_headers is filtered_proxy_headers
    assert reverse_proxy._forwarded_request_headers is forwarded_request_headers
    assert reverse_proxy._is_streaming_response is is_streaming_response
    assert reverse_proxy._is_websocket_upgrade is is_websocket_upgrade
    assert reverse_proxy._proxy_status_payload is proxy_status_payload
    assert reverse_proxy._restored_upstream_port is restored_upstream_port


def test_forwarded_request_headers_remove_hop_by_hop_and_add_forwarding_metadata():
    headers = {
        "Host": "example.com",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
        "X-Trace": "abc",
    }

    forwarded = forwarded_request_headers(
        headers,
        client_ip="203.0.113.5",
        scheme="https",
    )

    assert forwarded == {
        "Host": "example.com",
        "X-Trace": "abc",
        "X-Forwarded-For": "203.0.113.5",
        "X-Forwarded-Proto": "https",
    }


def test_filtered_proxy_headers_uses_case_insensitive_hop_by_hop_names():
    assert filtered_proxy_headers({
        "Upgrade": "websocket",
        "Proxy-Authenticate": "Basic",
        "Content-Type": "text/plain",
    }) == {"Content-Type": "text/plain"}


def test_websocket_upgrade_detection_preserves_existing_exact_connection_match():
    assert is_websocket_upgrade({"Upgrade": "WebSocket"})
    assert is_websocket_upgrade({"Connection": "Upgrade"})
    assert not is_websocket_upgrade({"Connection": "keep-alive, Upgrade"})


def test_streaming_response_detection_matches_chunked_or_event_stream_headers():
    assert is_streaming_response({"Transfer-Encoding": "Chunked"})
    assert is_streaming_response({"Content-Type": "text/event-stream; charset=utf-8"})
    assert not is_streaming_response({"Content-Type": "application/json"})


def test_proxy_status_payload_preserves_control_endpoint_shape():
    state = reverse_proxy.ProxyState(upstream_port=8082)
    state.total_requests = 4
    state.active_requests = 2
    state._previous_port = 8081
    state._port_active[8081] = 1

    payload = proxy_status_payload(state)

    assert payload["upstream_port"] == 8082
    assert payload["upstream_url"] == "http://127.0.0.1:8082"
    assert payload["total_requests"] == 4
    assert payload["active_requests"] == 2
    assert payload["drain_active"] == 1
    assert payload["previous_port"] == 8081
    assert "switched_at" in payload


def test_restored_upstream_port_reads_json_or_keeps_default(tmp_path):
    missing = tmp_path / "missing.json"
    assert restored_upstream_port(missing, 8081) == (8081, False)

    state_file = tmp_path / "proxy_state.json"
    state_file.write_text('{"upstream_port": 8084}', encoding="utf-8")
    assert restored_upstream_port(state_file, 8081) == (8084, True)

    state_file.write_text("{bad json", encoding="utf-8")
    assert restored_upstream_port(state_file, 8081) == (8081, False)
