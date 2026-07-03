import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from jane_web.ra_reports import RA_REPORT_TOKEN_SECONDS, RaReportAccess


def _request(headers: dict[str, str] | None = None, host: str = "10.0.0.8") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in (headers or {}).items()
            ],
            "client": (host, 12345),
            "query_string": b"",
        }
    )


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Real-IP")
        or (forwarded_for.split(",")[0].strip() if forwarded_for else "")
        or (request.client.host if request.client else "unknown")
    )


def _unauthorized(_request: Request) -> str:
    raise HTTPException(status_code=401, detail="Not authenticated")


def _authorized(_request: Request) -> str:
    return "session-1"


def _access(tmp_path, *, now: float = 1_800_000_000.0, require_auth=_authorized) -> RaReportAccess:
    return RaReportAccess(
        tmp_path,
        session_secret_provider=lambda: "test-secret",
        client_ip=_client_ip,
        require_auth=require_auth,
        now=lambda: now,
    )


def test_report_path_validation_and_latest_selection(tmp_path):
    older = tmp_path / "ra_research_run_20260701_010203.html"
    newer = tmp_path / "ra_research_run_20260702_010203.html"
    ignored = tmp_path / "ra_research_run_latest.html"
    older.write_text("older")
    newer.write_text("newer")
    ignored.write_text("ignored")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    access = _access(tmp_path)

    assert access.html_path("20260701_010203") == older
    assert access.latest_html_path() == newer
    assert access.report_id_from_html_path(newer) == "20260702_010203"
    assert access.report_id_from_html_path(ignored) == ""

    with pytest.raises(HTTPException) as bad_id:
        access.html_path("latest")
    assert bad_id.value.status_code == 404

    with pytest.raises(HTTPException) as missing:
        access.html_path("20260703_010203")
    assert missing.value.status_code == 404


def test_metadata_and_tokenized_announcement_grant_temporary_access(tmp_path):
    report_path = tmp_path / "ra_research_run_20260702_010203.html"
    report_path.write_text("<html>ok</html>")
    os.utime(report_path, (200, 200))
    request = _request({"CF-Connecting-IP": "203.0.113.9"})
    access = _access(tmp_path, require_auth=_unauthorized)

    metadata = access.metadata(report_path, request)
    assert metadata["id"] == "ra_report_20260702_010203_signed"
    assert metadata["report_url"].startswith("/api/research/ra/reports/20260702_010203.html?rt=")
    assert metadata["access_expires_in_seconds"] == RA_REPORT_TOKEN_SECONDS
    assert access.require_access(request, "20260702_010203", None) == "temporary_report_access"

    token = metadata["report_url"].split("rt=", 1)[1]
    assert access.valid_token("20260702_010203", token)

    item = {"type": "report_ready", "report_id": "20260702_010203", "message": "ready"}
    tokenized = access.tokenize_report_item(item, request)
    assert tokenized is not item
    assert tokenized["id"] == "ra_report_20260702_010203_signed"
    assert tokenized["report_url"].startswith("/api/research/ra/reports/20260702_010203.html?rt=")


def test_require_access_prefers_authenticated_session(tmp_path):
    access = _access(tmp_path, require_auth=_authorized)

    assert access.require_access(_request(), "20260702_010203", None) == "session-1"
