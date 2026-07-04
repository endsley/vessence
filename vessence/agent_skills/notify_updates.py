#!/usr/bin/env python3
import os
import json
import httpx
import asyncio
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import PENDING_UPDATES_PATH
from agent_skills.cron_utils import load_cron_env
from agent_skills.model_update_helpers import (
    discord_bot_headers as _discord_bot_headers,
    discord_channel_messages_url as _discord_channel_messages_url,
    discord_message_payload as _discord_message_payload,
    model_update_notification_message as _model_update_notification_message,
)

NOTIFY_FILE = PENDING_UPDATES_PATH
_env = load_cron_env()

DISCORD_TOKEN = _env["DISCORD_TOKEN"]
CHANNEL_ID = _env["DISCORD_CHANNEL_ID"]

async def send_notification():
    if not os.path.exists(NOTIFY_FILE):
        return

    try:
        with open(NOTIFY_FILE, "r") as f:
            data = json.load(f)
        
        message = _model_update_notification_message(data)

        # Simple Discord webhook-like POST using bot token
        url = _discord_channel_messages_url(CHANNEL_ID)
        headers = _discord_bot_headers(DISCORD_TOKEN)
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=_discord_message_payload(message))
            if resp.status_code == 200:
                print("Notification sent to Discord.")
                # Clear the notification so we don't spam
                os.remove(NOTIFY_FILE)
            else:
                print(f"Failed to send Discord message: {resp.text}")

    except Exception as e:
        print(f"Error in notification script: {e}")

if __name__ == "__main__":
    asyncio.run(send_notification())
