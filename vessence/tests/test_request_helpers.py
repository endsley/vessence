from types import SimpleNamespace

from jane_web.request_helpers import (
    client_ip,
    cookie_secure_flag,
    is_android_webview_request,
    is_local_browser_access,
    is_local_request,
    is_single_user_no_auth_mode,
    session_log_id,
)


def _request(*, headers=None, host="203.0.113.5", scheme="http"):
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(
        headers=headers or {},
        client=client,
        url=SimpleNamespace(scheme=scheme),
    )


def test_session_log_id_truncates_or_uses_none_label():
    assert session_log_id("1234567890abcdef") == "1234567890ab"
    assert session_log_id("") == "none"
    assert session_log_id(None) == "none"


def test_client_ip_prefers_cloudflare_then_real_ip_then_client_host():
    assert client_ip(_request(headers={"CF-Connecting-IP": "198.51.100.1"})) == "198.51.100.1"
    assert client_ip(_request(headers={"X-Real-IP": "198.51.100.2"})) == "198.51.100.2"
    assert client_ip(_request(host="127.0.0.1")) == "127.0.0.1"
    assert client_ip(_request(host=None)) == "unknown"


def test_cookie_secure_flag_uses_scheme_or_forwarded_proto_first_value():
    assert cookie_secure_flag(_request(scheme="https"))
    assert cookie_secure_flag(_request(headers={"x-forwarded-proto": "https, http"}))
    assert not cookie_secure_flag(_request(headers={"x-forwarded-proto": "http, https"}))
    assert not cookie_secure_flag(_request())


def test_local_browser_access_rejects_cloudflare_and_allows_loopback_hosts():
    assert is_local_browser_access(_request(host="127.0.0.1"))
    assert is_local_browser_access(_request(host="::1"))
    assert not is_local_browser_access(_request(host="localhost"))
    assert not is_local_browser_access(_request(headers={"cf-connecting-ip": "198.51.100.1"}, host="127.0.0.1"))


def test_single_user_no_auth_mode_depends_on_google_client_id():
    assert is_single_user_no_auth_mode({})
    assert is_single_user_no_auth_mode({"GOOGLE_CLIENT_ID": "   "})
    assert not is_single_user_no_auth_mode({"GOOGLE_CLIENT_ID": "client-id"})


def test_local_request_rejects_proxy_headers_and_allows_localhost_name():
    assert is_local_request(_request(host="localhost"))
    assert not is_local_request(_request(headers={"cf-connecting-ip": "198.51.100.1"}, host="127.0.0.1"))
    assert not is_local_request(_request(headers={"x-forwarded-for": "198.51.100.1"}, host="127.0.0.1"))
    assert not is_local_request(_request(host="203.0.113.5"))


def test_android_webview_request_detects_vessences_user_agent():
    assert is_android_webview_request(_request(headers={"user-agent": "VessencesAndroid/1.2"}))
    assert not is_android_webview_request(_request(headers={"user-agent": "Mozilla/5.0"}))
