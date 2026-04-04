#!/usr/bin/env python3
"""
cron_utils.py — Shared utilities for cron-invoked scripts.

Centralises Discord/work-log notification sending and .env loading so
individual cron scripts don't duplicate the same boilerplate.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import ENV_FILE_PATH, VESSENCE_HOME, VESSENCE_DATA_HOME, LOGS_DIR


def send_discord(message: str, webhook_url: str | None = None):
    """Send a notification.

    Discord is currently disconnected, so this redirects to the work log.
    If a *webhook_url* is supplied, it will attempt a real Discord webhook
    POST first and fall back to the work log on failure.
    """
    if webhook_url:
        try:
            import requests
            resp = requests.post(
                webhook_url,
                json={"content": message[:2000]},
                timeout=10,
            )
            if resp.ok:
                return
        except Exception:
            pass  # fall through to work-log

    try:
        from agent_skills.work_log_tools import log_activity
        clean = message.replace("**", "").replace("```", "").strip()
        if clean:
            log_activity(clean[:300], category="notification")
    except Exception:
        pass


def load_cron_env() -> dict:
    """Load the shared .env file and return a dict of common env vars.

    Returns keys: DISCORD_TOKEN, DISCORD_CHANNEL_ID, VESSENCE_HOME,
    VESSENCE_DATA_HOME, LOGS_DIR, plus anything else in the .env file.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE_PATH)
    except Exception:
        pass

    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN", ""),
        "DISCORD_CHANNEL_ID": os.getenv("DISCORD_CHANNEL_ID", ""),
        "VESSENCE_HOME": VESSENCE_HOME,
        "VESSENCE_DATA_HOME": VESSENCE_DATA_HOME,
        "LOGS_DIR": LOGS_DIR,
    }
