"""Pure helpers for Jane web CLI login flows."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from jane.config import normalize_frontier_provider


CLI_LOGIN_IGNORED_PORTS = frozenset({8081, 8090, 8080, 8082, 8083, 8000, 3000, 53, 631, 11434})
PROC_NET_IPV4_LOCALHOST = frozenset({"0100007F", "00000000"})
PROC_NET_IPV6_LOCALHOST = frozenset({
    "00000000000000000000000001000000",
    "00000000000000000000000000000000",
})
CLAUDE_TOKEN_RATE_LIMIT_ERROR = (
    "Token exchange failed: Anthropic's servers are rate-limiting requests for this application. "
    "This is a known issue. Please try again in a few minutes."
)
GEMINI_TOKEN_RATE_LIMIT_ERROR = (
    "Token exchange failed: Google's servers are rate-limiting requests for this application. "
    "Please try again in a few minutes."
)
CLAUDE_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_OAUTH_REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
CLAUDE_OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
GEMINI_OAUTH_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
GEMINI_OAUTH_REDIRECT_URI = "https://codeassist.google.com/authcode"
GEMINI_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


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


def base64url_no_padding(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_code_challenge(verifier: str) -> str:
    return base64url_no_padding(hashlib.sha256(verifier.encode()).digest())


def claude_oauth_authorization_url(code_challenge: str, state: str) -> str:
    return "https://claude.com/cai/oauth/authorize?" + urlencode({
        "code": "true",
        "client_id": CLAUDE_OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": CLAUDE_OAUTH_REDIRECT_URI,
        "scope": "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers user:file_upload",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    })


def gemini_oauth_authorization_url(code_challenge: str, state: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": GEMINI_OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": GEMINI_OAUTH_REDIRECT_URI,
        "access_type": "offline",
        "scope": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    })


def claude_auth_code_from_callback(code: str) -> str:
    return (code or "").split("#")[0].strip()


def claude_oauth_token_request_spec(auth_code: str, code_verifier: str) -> tuple[str, bytes, dict[str, str]]:
    return (
        CLAUDE_OAUTH_TOKEN_URL,
        urlencode({
            "grant_type": "authorization_code",
            "client_id": CLAUDE_OAUTH_CLIENT_ID,
            "code": auth_code,
            "code_verifier": code_verifier,
            "redirect_uri": CLAUDE_OAUTH_REDIRECT_URI,
        }).encode(),
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "claude-code/2.1.86",
            "Accept": "application/json",
        },
    )


def claude_oauth_refresh_request_spec(refresh_token: str) -> tuple[str, bytes, dict[str, str]]:
    return (
        CLAUDE_OAUTH_TOKEN_URL,
        urlencode({
            "grant_type": "refresh_token",
            "client_id": CLAUDE_OAUTH_CLIENT_ID,
            "refresh_token": refresh_token,
        }).encode(),
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "claude-code/2.1.86",
            "Accept": "application/json",
        },
    )


def gemini_oauth_token_request_spec(
    auth_code: str,
    code_verifier: str,
    *,
    client_secret: str,
) -> tuple[str, bytes, dict[str, str]]:
    return (
        GEMINI_OAUTH_TOKEN_URL,
        urlencode({
            "grant_type": "authorization_code",
            "client_id": GEMINI_OAUTH_CLIENT_ID,
            "client_secret": client_secret,
            "code": auth_code,
            "code_verifier": code_verifier,
            "redirect_uri": GEMINI_OAUTH_REDIRECT_URI,
        }).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )


def claude_credentials_payload(tokens: dict[str, Any], *, now_ms: int) -> dict[str, Any]:
    scopes = tokens.get("scope", "").split(" ") if tokens.get("scope") else []
    return {
        "claudeAiOauth": {
            "accessToken": tokens["access_token"],
            "refreshToken": tokens["refresh_token"],
            "expiresAt": now_ms + tokens.get("expires_in", 3600) * 1000,
            "scopes": scopes,
        }
    }


def claude_refresh_token_from_credentials(credentials: Mapping[str, Any]) -> str | None:
    refresh_token = credentials.get("claudeAiOauth", {}).get("refreshToken")
    return str(refresh_token) if refresh_token else None


def apply_claude_refresh_tokens(
    credentials: dict[str, Any],
    tokens: Mapping[str, Any],
    *,
    previous_refresh_token: str,
    now_ms: int,
) -> dict[str, Any]:
    oauth = credentials["claudeAiOauth"]
    scopes = tokens.get("scope", "").split(" ") if tokens.get("scope") else oauth.get("scopes", [])
    oauth.update({
        "accessToken": tokens["access_token"],
        "refreshToken": tokens.get("refresh_token", previous_refresh_token),
        "expiresAt": now_ms + tokens.get("expires_in", 3600) * 1000,
        "scopes": scopes,
    })
    return credentials


def gemini_credentials_payload(tokens: dict[str, Any], *, client_secret: str) -> dict[str, str]:
    return {
        "type": "authorized_user",
        "client_id": GEMINI_OAUTH_CLIENT_ID,
        "client_secret": client_secret,
        "refresh_token": tokens.get("refresh_token", ""),
    }


def oauth_login_credentials_for_code(
    provider: str,
    code: str,
    code_verifier: str,
    *,
    now_ms: int,
    request_factory: Callable[..., Any],
    urlopen_fn: Callable[..., Any],
    client_secret: str = "",
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    """Exchange a submitted OAuth login code for provider credentials."""
    provider = normalize_frontier_provider(provider)
    if provider == "claude":
        auth_code = claude_auth_code_from_callback(code)
        if not auth_code:
            return None, 400, "Invalid code format."
        token_url, token_data, token_headers = claude_oauth_token_request_spec(
            auth_code,
            code_verifier,
        )
    elif provider == "gemini":
        token_url, token_data, token_headers = gemini_oauth_token_request_spec(
            (code or "").strip(),
            code_verifier,
            client_secret=client_secret,
        )
    else:
        raise ValueError(f"Unsupported OAuth login provider: {provider}")

    tokens, last_exc = oauth_token_response(
        token_url,
        token_data,
        token_headers,
        request_factory=request_factory,
        urlopen_fn=urlopen_fn,
    )
    if not tokens:
        status_code, error = oauth_token_exchange_error(provider, last_exc)
        return None, status_code, error

    if provider == "claude":
        return claude_credentials_payload(tokens, now_ms=now_ms), None, None
    return gemini_credentials_payload(tokens, client_secret=client_secret), None, None


def cli_credentials_path(provider: str, *, home_path: Path | None = None) -> Path:
    provider = normalize_frontier_provider(provider)
    home_path = home_path or Path.home()
    if provider == "claude":
        return home_path / ".claude" / ".credentials.json"
    if provider == "gemini":
        return home_path / ".gemini" / "oauth_creds.json"
    raise ValueError(f"Unsupported CLI credentials provider: {provider}")


def write_cli_credentials(provider: str, credentials: dict[str, Any]) -> Path:
    credentials_path = cli_credentials_path(provider)
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(json.dumps(credentials), encoding="utf-8")
    credentials_path.chmod(0o600)
    return credentials_path


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


def provider_auth_status_details(
    provider: str,
    *,
    cache: MutableMapping[str, tuple[float, dict]],
    now_fn: Callable[[], float],
    run_command_fn: Callable[[list[str]], Any],
    attempt_refresh_fn: Callable[[], bool],
) -> dict:
    provider = normalize_frontier_provider(provider)
    now = now_fn()
    if provider in cache:
        ts, details = cache[provider]
        if now - ts < 5:
            return details

    cmd = provider_auth_status_command(provider)
    if not cmd:
        return unsupported_provider_auth_status(provider)
    try:
        result = run_command_fn(cmd)
    except Exception as exc:
        return provider_auth_status_error(provider, exc)

    details = provider_auth_status_base(provider, result.returncode)
    if result.returncode != 0:
        append_status_stderr_tail(details, result.stderr or "")
        return details

    output = (result.stdout or "").strip()
    if not output:
        return details

    parse_provider_auth_status_output(details, output)

    if not details.get("logged_in") and provider == "claude" and attempt_refresh_fn():
        try:
            result = run_command_fn(cmd)
            if result.returncode == 0:
                output = (result.stdout or "").strip()
                parse_provider_auth_status_output(details, output)
        except Exception:
            pass

    cache[provider] = (now, details)
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


def proc_net_listen_socket_ports(
    lines: Any,
    *,
    known_ports: set[int] | frozenset[int] = CLI_LOGIN_IGNORED_PORTS,
) -> list[tuple[int, int]]:
    entries: list[tuple[int, int]] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 10 or parts[3] != "0A":
            continue
        try:
            ip_hex, port_hex = parts[1].split(":")
            port = int(port_hex, 16)
            inode = int(parts[9])
        except (ValueError, IndexError):
            continue
        if ip_hex not in PROC_NET_IPV4_LOCALHOST and ip_hex not in PROC_NET_IPV6_LOCALHOST:
            continue
        if port in known_ports:
            continue
        entries.append((port, inode))
    return entries


def proc_net_listen_socket_candidates(
    tcp_paths: Any,
    *,
    known_ports: set[int] | frozenset[int] = CLI_LOGIN_IGNORED_PORTS,
    open_fn: Callable[[Any], Any] = open,
) -> tuple[list[int], dict[int, int]]:
    """Return unique listen ports and inode-to-port map from `/proc/net/tcp*` files."""
    candidate_ports: list[int] = []
    inode_to_port: dict[int, int] = {}
    for tcp_path in tcp_paths:
        try:
            with open_fn(tcp_path) as lines:
                for port, inode in proc_net_listen_socket_ports(lines, known_ports=known_ports):
                    if port not in candidate_ports:
                        candidate_ports.append(port)
                    inode_to_port[inode] = port
        except FileNotFoundError:
            continue
    return candidate_ports, inode_to_port


def ss_login_callback_port(
    lines: Any,
    *,
    known_ports: set[int] | frozenset[int] = CLI_LOGIN_IGNORED_PORTS,
) -> int | None:
    """Return a Claude/Node localhost callback port from `ss -tlnp` output."""
    for line in lines:
        if "claude" not in line and "node" not in line:
            continue
        match = re.search(r"127\.0\.0\.1:(\d+)", line)
        if not match:
            continue
        port = int(match.group(1))
        if port not in known_ports:
            return port
    return None


def proc_stat_parent_pid(stat_text: str) -> int | None:
    """Parse the parent pid from `/proc/<pid>/stat` text."""
    match = re.search(r"\)\s+\S+\s+(\d+)", stat_text)
    if not match:
        return None
    return int(match.group(1))


def process_ids_with_children(proc_root: Path, root_pid: int) -> list[int]:
    """Return the login process pid plus children found in one `/proc` scan."""
    pids_to_check = [root_pid]
    try:
        entries = proc_root.iterdir()
    except (OSError, PermissionError):
        return pids_to_check

    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            parent_pid = proc_stat_parent_pid((entry / "stat").read_text())
        except (OSError, PermissionError, ValueError):
            continue
        if parent_pid in pids_to_check:
            pids_to_check.append(int(entry.name))
    return pids_to_check


def process_tree_socket_port(
    root_pid: int,
    inode_to_port: dict[int, int],
    *,
    proc_root: Path = Path("/proc"),
    readlink_fn: Callable[[str], str] = os.readlink,
) -> int | None:
    """Return the first matching listen port owned by a process-tree socket fd."""
    for pid in process_ids_with_children(proc_root, root_pid):
        fd_dir = proc_root / str(pid) / "fd"
        if not fd_dir.exists():
            continue
        try:
            fds = fd_dir.iterdir()
        except (OSError, PermissionError):
            continue
        for fd in fds:
            try:
                target = readlink_fn(str(fd))
            except (OSError, PermissionError):
                continue
            match = re.match(r"socket:\[(\d+)\]", target)
            if not match:
                continue
            inode = int(match.group(1))
            if inode in inode_to_port:
                return inode_to_port[inode]
    return None


def oauth_token_exchange_error(provider: str, exc: BaseException | None) -> tuple[int, str]:
    detail = str(exc) if exc is not None else "No token response"
    if hasattr(exc, "read"):
        try:
            error_body = exc.read().decode()
        except Exception:
            error_body = ""
        if error_body:
            provider = normalize_frontier_provider(provider)
            if provider == "claude":
                try:
                    error_json = json.loads(error_body)
                    if error_json.get("error", {}).get("type") == "rate_limit_error":
                        return 429, CLAUDE_TOKEN_RATE_LIMIT_ERROR
                except Exception:
                    pass
            if provider == "gemini" and "rateLimitExceeded" in error_body:
                return 429, GEMINI_TOKEN_RATE_LIMIT_ERROR
            detail = error_body[:300]
    return 400, f"Token exchange failed: {detail}"


def oauth_token_response(
    token_url: str,
    token_data: bytes,
    token_headers: dict[str, str],
    *,
    request_factory: Callable[..., Any],
    urlopen_fn: Callable[..., Any],
    timeout: int = 15,
) -> tuple[Any | None, BaseException | None]:
    """Fetch and decode an OAuth token response, preserving any exception."""
    try:
        token_req = request_factory(
            token_url,
            data=token_data,
            headers=token_headers,
        )
        token_resp = urlopen_fn(token_req, timeout=timeout)
        return json.loads(token_resp.read()), None
    except Exception as exc:
        return None, exc


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


def cli_login_output_update(
    line: str,
    *,
    auth_url: str | None,
    device_code: str | None,
) -> tuple[str | None, str | None, str | None]:
    stripped = line.strip()
    if not auth_url:
        auth_url = extract_first_auth_url(line)
    if auth_url and not device_code:
        extracted_device_code = extract_device_code(stripped)
        if extracted_device_code:
            device_code = extracted_device_code
    return auth_url, device_code, stripped or None


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


def submit_cli_login_code_to_stdin(process: Any, code: str) -> tuple[bool, str | None, int | None]:
    """Write an auth code to a CLI login process stdin."""
    if not getattr(process, "stdin", None):
        return False, "This login session does not accept code entry.", 400
    try:
        process.stdin.write(code + "\n")
        process.stdin.flush()
    except Exception as exc:
        return False, f"Could not submit authentication code: {exc}", 500
    return True, None, None


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
