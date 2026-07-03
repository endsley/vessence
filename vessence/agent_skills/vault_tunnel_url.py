#!/usr/bin/env python3
"""vault_tunnel_url.py — Report the current Cloudflare tunnel URL for the Vault website."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills.vault_tunnel_helpers import (
    select_vault_url as _select_vault_url,
    trycloudflare_url_from_lines as _trycloudflare_url_from_lines,
    vault_url_output as _vault_url_output,
)
from jane.config import VAULT_TUNNEL_LOG

LOG_PATHS = [
    VAULT_TUNNEL_LOG,
    "/tmp/vault_tunnel.log",
]


FIXED_VAULT_URL = "https://vault.vessences.com"
FIXED_JANE_URL  = "https://jane.vessences.com"


def get_tunnel_url() -> str:
    # Check env override first
    selected = _select_vault_url(os.environ.get("VAULT_URL"), FIXED_VAULT_URL)
    if selected:
        return selected
    # Fixed domain is configured — return it directly
    # Fallback: scan log for legacy quick tunnel URL
    for log_path in LOG_PATHS:
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    found = _trycloudflare_url_from_lines(f.readlines())
                    if found:
                        return found
            except Exception:
                pass
    return None


def main():
    url = get_tunnel_url()
    print(_vault_url_output(url, FIXED_JANE_URL))


if __name__ == "__main__":
    main()
