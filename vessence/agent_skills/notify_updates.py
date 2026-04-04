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
        
        message = (
            f"🚀 **New Model Upgrade Detected!**\n\n"
            f"**Model:** {data['model_name']}\n"
            f"**Improvements:**\n{data['key_improvements']}\n\n"
            f"**Source:** {data['source_url']}\n\n"
            f"Should we discuss upgrading our brains to this new model?"
        )

        # Simple Discord webhook-like POST using bot token
        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json={"content": message})
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
