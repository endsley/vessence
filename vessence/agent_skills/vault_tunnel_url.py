#!/usr/bin/env python3
"""vault_tunnel_url.py — Report the current Cloudflare tunnel URL for the Vault website."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import VAULT_TUNNEL_LOG

LOG_PATHS = [
    VAULT_TUNNEL_LOG,
    "/tmp/vault_tunnel.log",
]


FIXED_VAULT_URL = "https://vault.vessences.com"
FIXED_JANE_URL  = "https://jane.vessences.com"


def get_tunnel_url() -> str:
    # Check env override first
    env_url = os.environ.get("VAULT_URL")
    if env_url:
        return env_url
    # Fixed domain is configured — return it directly
    if FIXED_VAULT_URL:
        return FIXED_VAULT_URL
    # Fallback: scan log for legacy quick tunnel URL
    for log_path in LOG_PATHS:
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    for line in reversed(f.readlines()):
                        if "trycloudflare.com" in line:
                            match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                            if match:
                                return match.group(0)
            except Exception:
                pass
    return None


def main():
    url = get_tunnel_url()
    if url:
        print(f"Vault URL: {url}")
        print(f"Jane URL:  {FIXED_JANE_URL}")
    else:
        print("Vault tunnel URL not available. Is the tunnel running?")


if __name__ == "__main__":
    main()
