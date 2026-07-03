"""Pure helpers for vault_tunnel_url.py."""

from __future__ import annotations

import re


TRYCLOUDFLARE_RE = re.compile(r"https://[\w\-]+\.trycloudflare\.com")


def trycloudflare_url_from_lines(lines: list[str]) -> str | None:
    for line in reversed(lines):
        if "trycloudflare.com" not in line:
            continue
        match = TRYCLOUDFLARE_RE.search(line)
        if match:
            return match.group(0)
    return None


def select_vault_url(env_url: str | None, fixed_url: str | None) -> str | None:
    if env_url:
        return env_url
    if fixed_url:
        return fixed_url
    return None


def vault_url_output(url: str | None, jane_url: str) -> str:
    if url:
        return f"Vault URL: {url}\nJane URL:  {jane_url}"
    return "Vault tunnel URL not available. Is the tunnel running?"
