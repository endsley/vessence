"""Pure helpers for Jane web CLI login flows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from jane.config import normalize_frontier_provider


def cli_login_candidates(provider: str) -> list[list[str]]:
    provider = normalize_frontier_provider(provider)
    if provider == "claude":
        # Claude: self-managed OAuth (bypass CLI, handled in /api/cli-login).
        return [["claude", "auth", "login"]]
    if provider == "gemini":
        return [["gemini", "auth", "login"]]
    if provider == "openai":
        # Codex: device-auth flow works in Docker (no localhost callback needed).
        return [["codex", "login", "--device-auth"]]
    return []


def cli_binary_for_provider(provider: str) -> str | None:
    candidates = cli_login_candidates(provider)
    return candidates[0][0] if candidates else None


def mask_email(value: str) -> str:
    if "@" not in value:
        return value[:3] + "..." if value else ""
    local, domain = value.split("@", 1)
    local_masked = (local[:2] + "***") if local else "***"
    return f"{local_masked}@{domain}"


def parse_provider_auth_status_output(details: dict, output: str) -> bool:
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            details["logged_in"] = bool(parsed.get("loggedIn"))
            if parsed.get("authMethod"):
                details["auth_method"] = parsed.get("authMethod")
            if parsed.get("email"):
                details["email_hint"] = mask_email(str(parsed.get("email")))
            if parsed.get("subscriptionType"):
                details["subscription_type"] = parsed.get("subscriptionType")
            return True
    except Exception:
        pass
    lowered = output.lower()
    details["logged_in"] = "logged in" in lowered and "not logged in" not in lowered
    details["status_stdout_tail"] = output.splitlines()[-1][:200]
    return True


def provider_auth_status_command(provider: str) -> list[str] | None:
    provider = normalize_frontier_provider(provider)
    if provider == "claude":
        return ["claude", "auth", "status"]
    return None


def unsupported_provider_auth_status(provider: str) -> dict:
    return {"provider": provider, "supported": False, "logged_in": False}


def provider_auth_status_error(provider: str, exc: Exception) -> dict:
    return {
        "provider": provider,
        "supported": True,
        "logged_in": False,
        "status_error": str(exc),
    }


def provider_auth_status_base(provider: str, returncode: int) -> dict:
    return {
        "provider": provider,
        "supported": True,
        "status_returncode": returncode,
        "logged_in": False,
    }


def append_status_stderr_tail(details: dict, stderr: str) -> dict:
    stderr = (stderr or "").strip()
    if stderr:
        details["status_stderr_tail"] = stderr.splitlines()[-1][:200]
    return details


def extract_oauth_state(auth_url: str) -> str | None:
    """Extract the state parameter from an OAuth URL."""
    if not auth_url:
        return None
    try:
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)
        states = params.get("state", [])
        return states[0] if states else None
    except Exception:
        return None


def clean_cli_output(raw_output: bytes) -> str:
    clean = re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', raw_output)
    clean = re.sub(rb'\x1b\][^\x07]*\x07', b'', clean)
    clean = re.sub(rb'\x1b\]8;[^\x1b]*\x1b\\\\?', b'', clean)
    return clean.decode("utf-8", errors="replace")


def cli_output_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_claude_auth_url(output_lines: list[str]) -> str | None:
    url_pattern = re.compile(r"https?://\S+")
    for line in output_lines:
        match = url_pattern.search(line)
        if match:
            candidate = match.group(0).rstrip(")").rstrip("\\")
            if "claude.com" in candidate or "anthropic.com" in candidate:
                return candidate
    return None


def extract_first_auth_url(line: str) -> str | None:
    for word in line.split():
        if word.startswith("http://") or word.startswith("https://"):
            return word.strip().rstrip(")")
    return None


def extract_device_code(text: str) -> str | None:
    match = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4,6})\b", text)
    return match.group(1) if match else None


def read_cli_transcript_lines(path: str | None) -> list[str]:
    if not path:
        return []
    transcript = Path(path)
    if not transcript.exists():
        return []
    return [
        line.strip()
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def cli_login_process_state(process: Any) -> tuple[str, int | None]:
    if process is None:
        return "missing", None
    polled = process.poll()
    return ("running" if polled is None else "exited"), process.returncode


def cli_login_debug_payload(
    *,
    provider: str,
    process: Any,
    authenticated: bool,
    transcript_lines: list[str],
    auth_status: dict,
) -> dict:
    process_state, returncode = cli_login_process_state(process)
    return {
        "provider": provider,
        "process_state": process_state,
        "process_returncode": returncode,
        "cli_login_authenticated_flag": authenticated,
        "transcript_tail": transcript_lines[-3:],
        "auth_status": auth_status,
    }
