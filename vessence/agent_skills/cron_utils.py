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

from agent_skills.cron_notification_helpers import (
    cron_env_payload as _cron_env_payload,
    discord_webhook_payload as _discord_webhook_payload,
    work_log_notification_text as _work_log_notification_text,
)
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
                json=_discord_webhook_payload(message),
                timeout=10,
            )
            if resp.ok:
                return
        except Exception:
            pass  # fall through to work-log

    try:
        from agent_skills.work_log_tools import log_activity
        clean = _work_log_notification_text(message)
        if clean:
            log_activity(clean, category="notification")
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

    return _cron_env_payload(
        os.environ,
        vessence_home=VESSENCE_HOME,
        vessence_data_home=VESSENCE_DATA_HOME,
        logs_dir=LOGS_DIR,
    )
