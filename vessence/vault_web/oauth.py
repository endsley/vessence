"""oauth.py — Google OAuth shared setup for vault_web and jane_web."""
import os
from urllib.parse import urljoin

from authlib.integrations.starlette_client import OAuth


def _normalized_email(value: str) -> str:
    return (value or "").strip().lower()


def _configured_value(env_name: str) -> str:
    return (os.getenv(env_name) or "").strip()


def _configured_public_base_url(*env_names: str) -> str:
    for env_name in env_names:
        value = _configured_value(env_name)
        if value:
            return value.rstrip("/")
    return ""


def google_oauth_configured() -> bool:
    """Return True when the Google OAuth client and allowlist are configured."""
    return bool(
        _configured_value("GOOGLE_CLIENT_ID")
        and _configured_value("GOOGLE_CLIENT_SECRET")
        and _configured_value("ALLOWED_GOOGLE_EMAILS")
    )


oauth = OAuth()
oauth.register(
    name="google",
    client_id=_configured_value("GOOGLE_CLIENT_ID") or None,
    client_secret=_configured_value("GOOGLE_CLIENT_SECRET") or None,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.modify",
        "access_type": "offline",
        "prompt": "consent",
    },
)


def build_external_url(request, path: str, *env_names: str) -> str:
    """Build a public-facing absolute URL, even when running behind a proxy."""
    base_url = _configured_public_base_url(*env_names, "PUBLIC_BASE_URL", "APP_PUBLIC_BASE_URL")
    if not base_url:
        forwarded_proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
        forwarded_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
        forwarded_prefix = (request.headers.get("x-forwarded-prefix") or "").split(",")[0].strip().rstrip("/")
        base_url = f"{forwarded_proto}://{forwarded_host}{forwarded_prefix}"
    return urljoin(f"{base_url}/", path.lstrip("/"))


def allowed_email(email: str) -> bool:
    """Check if the Google account email is permitted to log in."""
    normalized = _normalized_email(email)
    allowed = {
        _normalized_email(candidate)
        for candidate in os.getenv("ALLOWED_GOOGLE_EMAILS", "").split(",")
        if candidate.strip()
    }
    return normalized in allowed
