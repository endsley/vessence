"""RA research report access helpers for Jane web routes."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, Request


RA_REPORT_ID_RE = re.compile(r"^\d{8}_\d{6}$")
RA_REPORT_GRANT_SECONDS = 45 * 60
RA_REPORT_TOKEN_SECONDS = 7 * 24 * 60 * 60
RA_REPORT_SHARE_TOKEN_HEX = 32


class RaReportAccess:
    """Token and recent-grant access control for local RA HTML reports."""

    def __init__(
        self,
        html_reports_dir: Path,
        session_secret_provider: Callable[[], str],
        client_ip: Callable[[Request], str],
        require_auth: Callable[[Request], str],
        *,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.html_reports_dir = html_reports_dir
        self._session_secret_provider = session_secret_provider
        self._client_ip = client_ip
        self._require_auth = require_auth
        self._now = now
        self._recent_grants: dict[tuple[str, str], float] = {}

    @staticmethod
    def report_id_from_html_path(path: Path) -> str:
        report_id = path.stem.removeprefix("ra_research_run_")
        return report_id if RA_REPORT_ID_RE.match(report_id) else ""

    def html_path(self, report_id: str) -> Path:
        if not RA_REPORT_ID_RE.match(report_id):
            raise HTTPException(status_code=404, detail="Report not found")
        path = self.html_reports_dir / f"ra_research_run_{report_id}.html"
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Report not found")
        return path

    def latest_html_path(self) -> Path:
        if not self.html_reports_dir.exists():
            raise HTTPException(status_code=404, detail="No RA reports found")
        reports = [
            path
            for path in self.html_reports_dir.glob("ra_research_run_*.html")
            if path.is_file() and self.report_id_from_html_path(path)
        ]
        if not reports:
            raise HTTPException(status_code=404, detail="No RA reports found")
        return max(reports, key=lambda path: path.stat().st_mtime)

    def prune_grants(self) -> None:
        now = self._now()
        stale = [key for key, expires_at in self._recent_grants.items() if expires_at <= now]
        for key in stale:
            self._recent_grants.pop(key, None)

    def grant_access(self, request: Request, report_id: str) -> None:
        self.prune_grants()
        self._recent_grants[(self._client_ip(request), report_id)] = self._now() + RA_REPORT_GRANT_SECONDS

    def has_recent_grant(self, request: Request, report_id: str) -> bool:
        self.prune_grants()
        return self._recent_grants.get((self._client_ip(request), report_id), 0) > self._now()

    def sign_token(self, report_id: str, expires_at: int) -> str:
        secret = self._session_secret_provider()
        message = f"{report_id}:{expires_at}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    def issue_token(self, report_id: str) -> str:
        expires_at = int(self._now() + RA_REPORT_TOKEN_SECONDS)
        return f"{expires_at}.{self.sign_token(report_id, expires_at)}"

    def share_token(self, report_id: str) -> str:
        secret = self._session_secret_provider()
        message = f"share:{report_id}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()[:RA_REPORT_SHARE_TOKEN_HEX]

    def valid_share_token(self, report_id: str, token: Optional[str]) -> bool:
        if not token or not RA_REPORT_ID_RE.match(report_id):
            return False
        return hmac.compare_digest(token, self.share_token(report_id))

    def share_path(self, report_id: str) -> str:
        return f"/share/research/ra/reports/{report_id}/{self.share_token(report_id)}"

    def valid_token(self, report_id: str, token: Optional[str]) -> bool:
        if not token or "." not in token:
            return False
        expires_raw, _, supplied = token.partition(".")
        try:
            expires_at = int(expires_raw)
        except ValueError:
            return False
        if expires_at <= self._now():
            return False
        expected = self.sign_token(report_id, expires_at)
        return hmac.compare_digest(supplied, expected)

    def require_access(self, request: Request, report_id: str, token: Optional[str]) -> str:
        try:
            session_id = self._require_auth(request)
            self.grant_access(request, report_id)
            return session_id
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
            if self.valid_token(report_id, token) or self.has_recent_grant(request, report_id):
                return "temporary_report_access"
            raise

    def tokenize_report_item(self, item: dict, request: Request) -> dict:
        if item.get("type") != "report_ready":
            return item
        report_id = str(item.get("report_id") or "").strip()
        if not RA_REPORT_ID_RE.match(report_id):
            return item
        self.grant_access(request, report_id)
        token = self.issue_token(report_id)
        updated = dict(item)
        updated["id"] = f"ra_report_{report_id}_signed"
        updated["report_url"] = f"/api/research/ra/reports/{report_id}.html?rt={token}"
        updated["share_url"] = self.share_path(report_id)
        updated["access_expires_in_seconds"] = RA_REPORT_TOKEN_SECONDS
        return updated

    def metadata(self, path: Path, request: Request | None = None) -> dict:
        report_id = self.report_id_from_html_path(path)
        if not report_id:
            raise HTTPException(status_code=404, detail="Report not found")
        created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        report_url = f"/api/research/ra/reports/{report_id}.html"
        if request is not None:
            self.grant_access(request, report_id)
            report_url = f"{report_url}?rt={self.issue_token(report_id)}"
        return {
            "id": f"ra_report_{report_id}_signed",
            "type": "report_ready",
            "report_kind": "ra_research",
            "report_id": report_id,
            "title": "RA research update ready",
            "message": "Tap to read the latest RA research HTML report.",
            "created_at": created,
            "timestamp": created,
            "report_url": report_url,
            "web_url": f"/research/ra/reports/{report_id}",
            "share_url": self.share_path(report_id),
            "access_expires_in_seconds": RA_REPORT_TOKEN_SECONDS,
        }
