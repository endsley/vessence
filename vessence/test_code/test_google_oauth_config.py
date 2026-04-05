#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vault_web.oauth import allowed_email, build_external_url


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "scheme": "http",
        "method": "GET",
        "path": "/auth/google",
        "raw_path": b"/auth/google",
        "query_string": b"",
        "headers": headers or [(b"host", b"vault.internal")],
        "server": ("vault.internal", 8080),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_build_external_url_prefers_explicit_public_base_url(monkeypatch):
    monkeypatch.setenv("VAULT_PUBLIC_BASE_URL", "https://vault.vessences.com")
    request = _request()
    assert build_external_url(request, "/auth/google/callback", "VAULT_PUBLIC_BASE_URL") == (
        "https://vault.vessences.com/auth/google/callback"
    )


def test_build_external_url_uses_forwarded_headers(monkeypatch):
    monkeypatch.delenv("VAULT_PUBLIC_BASE_URL", raising=False)
    request = _request(
        [
            (b"host", b"vault.internal"),
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-host", b"vault.vessences.com"),
        ]
    )
    assert build_external_url(request, "/auth/google/callback", "VAULT_PUBLIC_BASE_URL") == (
        "https://vault.vessences.com/auth/google/callback"
    )


def test_allowed_email_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("ALLOWED_GOOGLE_EMAILS", "Owner@Vessences.com,second@example.com")
    assert allowed_email("owner@vessences.com") is True
    assert allowed_email("OWNER@VESSENCES.COM") is True
    assert allowed_email("other@example.com") is False
