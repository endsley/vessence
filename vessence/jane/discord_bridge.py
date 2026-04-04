# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import discord
import httpx
import os
import logging
import base64
import io
import json
import exifread
import sys
import fcntl
import time
import asyncio
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Import sorting logic from Amber's brain
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "amber"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.vault_tools import get_file_category
from jane.config import (
    VAULT_DIR, ADK_SERVER_URL, ADK_RUN_URL as AGENT_RUN_URL, AMBER_APP_NAME as APP_NAME,
    FALLBACK_SCRIPT, DISCORD_MAX_MSG_LEN, HTTP_TIMEOUT_DEFAULT, HTTP_TIMEOUT_ADK_RUN,
    HTTP_TIMEOUT_DISCORD, ENV_FILE_PATH,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bridge')

# Load environment
load_dotenv(ENV_FILE_PATH, override=True)
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID_STR = os.getenv('DISCORD_CHANNEL_ID')
DIAGNOSTIC_MODE = os.getenv('DIAGNOSTIC_MODE', 'false').lower() == 'true'
BRAIN_MODE = os.getenv('AMBER_BRAIN_MODEL', 'gemini').lower()
# Local models (gemma, qwen) may not emit a final text turn after tool calls
LOCAL_BRAIN = BRAIN_MODE in ('gemma', 'gemma3', 'qwen', 'qwen-local')

if not TOKEN:
    logger.error("FATAL: DISCORD_TOKEN is missing!")
    exit(1)

TOKEN = TOKEN.strip().replace('"', '').replace("'", "")
CHANNEL_ID = int(CHANNEL_ID_STR) if CHANNEL_ID_STR else 0

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class DiscordBridge(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processing_sessions = set()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Listening on channel {CHANNEL_ID}")
        if DIAGNOSTIC_MODE:
            logger.info("DIAGNOSTIC MODE: ENABLED")

    async def create_session(self, client, user_id, session_id):
        url = f"{ADK_SERVER_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
        resp = await client.post(url, json={}, timeout=HTTP_TIMEOUT_DEFAULT)
        if resp.status_code == 409:
            logger.info(f"Session {session_id} already exists.")
            return
        resp.raise_for_status()
        logger.info(f"Created new session: {session_id}")

    async def run_fallback(self, user_text):
        """Kicks off the DeepSeek -> OpenAI -> Qwen fallback chain."""
        try:
            logger.warning(f"Amber Brain Error. Triggering Fallback for: {user_text}")
            cmd = [FALLBACK_SCRIPT, user_text, "--identity", "amber"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode().strip()
            return clean_ansi(output) if output else "⚠️ Amber Brain and Fallback failed."
        except Exception as e:
            return f"⚠️ Fallback Error: {str(e)}"

    async def handle_fallback_attachments(self, message, fallback_text):
        """Scans fallback text for ATTACH: filename tags and sends them."""
        # 1. Look for ATTACH: <filename>
        matches = re.findall(r"ATTACH:\s*(\S+)", fallback_text)
        
        # If we ARE attaching, remove common "I can't" phrases that cause contradictions
        if matches:
            phrases_to_remove = [
                r"I'm currently operating as an emergency fallback brain, so I don't have direct access to display images right now.",
                r"While I can't display it visually in this interface,",
                r"I don't have direct access to display images right now.",
                r"I'm afraid I can't show you a picture,",
                r"as I don't have a physical form or visual representation.",
                r"I cannot display it visually,",
                r"I don't have the ability to show you pictures,",
                r"I am currently in fallback mode and cannot see images."
            ]
            for phrase in phrases_to_remove:
                fallback_text = re.sub(phrase, "", fallback_text, flags=re.IGNORECASE)

        clean_text = re.sub(r"ATTACH:\s*\S+", "", fallback_text).strip()
        
        # Send cleaned text first
        if clean_text:
            await message.channel.send(clean_text)
            
        # 2. Send files
        for filename in matches:
            # Search for file in subdirectories
            target_path = None
            for root, dirs, files in os.walk(VAULT_DIR):
                if filename in files:
                    target_path = os.path.join(root, filename)
                    break
            
            if target_path and os.path.exists(target_path):
                try:
                    await message.channel.send(file=discord.File(target_path))
                    logger.info(f"Fallback: Sent attachment {filename}")
                except Exception as e:
                    logger.error(f"Fallback: Failed to send {filename}: {e}")
            else:
                logger.warning(f"Fallback: Requested file {filename} not found in vault.")

    async def on_message(self, message):
        try:
            if message.author == self.user:
                return
                
            # Basic filters
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_main_channel = message.channel.id == CHANNEL_ID
            is_mention = self.user.mentioned_in(message) or self.user.name.lower() in message.content.lower()
            
            if not (is_dm or (is_main_channel and is_mention)):
                return

            # --- Concurrency Lock ---
            session_key = str(message.channel.id)
            if session_key in self.processing_sessions:
                return
            
            self.processing_sessions.add(session_key)
            try:
                user_text = message.content
                attachments = message.attachments

                if DIAGNOSTIC_MODE:
                    logger.info(f"DIAG: Raw Input from {message.author}: {user_text}")
                
                async with message.channel.typing():
                    parts = []
                    if user_text:
                        # Strip mention if present
                        cleaned_text = re.sub(rf'<@!?{self.user.id}>', '', user_text).strip()
                        parts.append({"text": cleaned_text})
                    
                    if attachments:
                        for attachment in attachments:
                            file_data = await attachment.read()
                            type_folder = get_file_category(attachment.filename)
                            target_dir = os.path.join(VAULT_DIR, type_folder)
                            os.makedirs(target_dir, exist_ok=True)
                            filename = attachment.filename
                            target_path = os.path.join(target_dir, filename)
                            with open(target_path, "wb") as f:
                                f.write(file_data)
                            logger.info(f"Attachment pre-saved to {target_path}")

                            # Tell Amber the file is already saved so vault_save
                            # doesn't try to re-encode binary content as text.
                            parts.append({"text": f"[ATTACHMENT_PRE_SAVED: '{filename}' → vault/{type_folder}/{filename}]"})

                            encoded_data = base64.b64encode(file_data).decode('utf-8')
                            parts.append({
                                "inline_data": {
                                    "mime_type": attachment.content_type or "application/octet-stream",
                                    "data": encoded_data
                                }
                            })

                    if not parts:
                        return

                    payload = {
                        "app_name": APP_NAME,
                        "user_id": str(message.author.id),
                        "session_id": str(message.channel.id),
                        "new_message": {"parts": parts, "role": "user"}
                    }

                    if DIAGNOSTIC_MODE:
                        logger.info(f"DIAG: Sending Payload: {json.dumps(payload)}")

                    async with httpx.AsyncClient() as client:
                        try:
                            response = await client.post(AGENT_RUN_URL, json=payload, timeout=HTTP_TIMEOUT_ADK_RUN)

                            if response.status_code == 404 and "Session not found" in response.text:
                                await self.create_session(client, str(message.author.id), str(message.channel.id))
                                response = await client.post(AGENT_RUN_URL, json=payload, timeout=HTTP_TIMEOUT_ADK_RUN)

                            if response.status_code == 500 and "stale session" in response.text.lower():
                                logger.warning("Stale session detected — deleting and recreating session.")
                                user_id = str(message.author.id)
                                session_id = str(message.channel.id)
                                del_url = f"{ADK_SERVER_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
                                await client.delete(del_url, timeout=HTTP_TIMEOUT_DISCORD)
                                await self.create_session(client, user_id, session_id)
                                response = await client.post(AGENT_RUN_URL, json=payload, timeout=HTTP_TIMEOUT_ADK_RUN)

                            if response.status_code != 200:
                                logger.error(f"Brain Error {response.status_code}: {response.text}")
                                fb_res = await self.run_fallback(cleaned_text if user_text else "Check status")
                                await self.handle_fallback_attachments(message, fb_res)
                                return

                            data = response.json()
                            if DIAGNOSTIC_MODE:
                                logger.info(f"DIAG: Received Response: {json.dumps(data)}")

                            events = data if isinstance(data, list) else data.get("events", [])

                            found_text = False

                            def find_and_send_attachments(obj, redact=False):
                                """Recursively extract file_data / inline_data from any event structure."""
                                if isinstance(obj, dict):
                                    if "inline_data" in obj:
                                        raw = obj["inline_data"].get("data")
                                        name = obj["inline_data"].get("display_name", "file")
                                        if raw:
                                            return [(io.BytesIO(base64.b64decode(raw)), name)]
                                    if "file_data" in obj:
                                        file_uri = obj["file_data"].get("file_uri")
                                        if file_uri and os.path.exists(file_uri):
                                            with open(file_uri, "rb") as fh:
                                                return [(io.BytesIO(fh.read()), os.path.basename(file_uri))]
                                    if "image" in obj and isinstance(obj["image"], dict):
                                        raw = obj["image"].get("data")
                                        if raw:
                                            return [(io.BytesIO(base64.b64decode(raw)), "screenshot.png")]
                                    results = []
                                    for value in obj.values():
                                        results.extend(find_and_send_attachments(value, redact))
                                    return results
                                elif isinstance(obj, (list, tuple)):
                                    results = []
                                    for item in obj:
                                        results.extend(find_and_send_attachments(item, redact))
                                    return results
                                return []

                            def unwrap_text(raw: str) -> str:
                                """Local models (gemma/qwen via LiteLLM) sometimes return text as
                                a JSON object like {"name":"response_text","content":"Hi"}.
                                Unwrap it to just the content string."""
                                if not LOCAL_BRAIN:
                                    return raw
                                stripped = raw.strip()
                                if stripped.startswith("{"):
                                    try:
                                        obj = json.loads(stripped)
                                        if isinstance(obj, dict):
                                            return obj.get("content") or obj.get("text") or obj.get("output") or raw
                                    except Exception:
                                        pass
                                return raw

                            def extract_text_from_parts(parts):
                                """Collect all non-empty text from a parts list, including functionResponse results."""
                                texts = []
                                for part in parts:
                                    # Direct text part
                                    if "text" in part and part["text"].strip():
                                        texts.append(unwrap_text(part["text"]))
                                    # For local models: text may be buried inside functionResponse result
                                    if LOCAL_BRAIN and "functionResponse" in part:
                                        resp = part["functionResponse"].get("response", {})
                                        result = resp.get("result") or resp.get("output") or []
                                        if isinstance(result, list):
                                            for item in result:
                                                if isinstance(item, dict) and item.get("text", "").strip():
                                                    texts.append(unwrap_text(item["text"]))
                                        elif isinstance(result, str) and result.strip():
                                            texts.append(unwrap_text(result))
                                return texts

                            for event in events:
                                author = event.get("author")
                                if author == "user":
                                    continue

                                header = ""
                                if author == "qwen_agent":
                                    header = "*(via Qwen)*\n\n"

                                if event.get("content"):
                                    parts = event["content"].get("parts", [])

                                    # Send all text parts
                                    for text in extract_text_from_parts(parts):
                                        full_message = f"{header}{text}"
                                        if len(full_message) > DISCORD_MAX_MSG_LEN:
                                            for i in range(0, len(full_message), DISCORD_MAX_MSG_LEN):
                                                await message.channel.send(full_message[i:i+DISCORD_MAX_MSG_LEN])
                                        else:
                                            await message.channel.send(full_message)
                                        found_text = True
                                        header = ""

                                # Send file attachments (scans entire event tree)
                                for f_io, name in find_and_send_attachments(event, redact=True):
                                    try:
                                        await message.channel.send(file=discord.File(fp=f_io, filename=name))
                                        found_text = True
                                    except Exception as e:
                                        logger.error(f"Failed to send discord file: {e}")

                                # Local brain: if the event had content but no text was extracted yet,
                                # mark as handled so we don't spuriously fall back to DeepSeek.
                                if LOCAL_BRAIN and event.get("content") and not found_text:
                                    found_text = True

                        except Exception as e:
                            logger.error(f"Bridge connection error [{type(e).__name__}]: {e}")
                            fb_res = await self.run_fallback(cleaned_text if user_text else "Check status")
                            await self.handle_fallback_attachments(message, fb_res)
                            return

                    # If ADK returned 200 OK but no text or attachments were sent, fallback
                    if not found_text:
                        logger.warning(f"ADK returned empty response (no text/attachments). Triggering fallback.")
                        fb_res = await self.run_fallback(cleaned_text if user_text else "Check status")
                        await self.handle_fallback_attachments(message, fb_res)

            finally:
                self.processing_sessions.remove(session_key)

        except Exception as e:
            logger.exception(f"Bridge handler error: {e}")
            await message.channel.send(f"Sorry, I encountered an error: {str(e)}")

def ensure_singleton():
    lock_file = "/tmp/amber_bridge.lock"
    f = open(lock_file, "w")  # noqa: SIM115 — intentionally kept open for lock lifetime
    try:
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f  # caller must keep reference to prevent GC / lock release
    except IOError:
        f.close()
        print("Another instance of Amber Bridge is already running. Exiting.")
        os._exit(0)

async def start_bridge():
    intents = discord.Intents.all()
    client = DiscordBridge(intents=intents, chunk_guilds_at_startup=True)
    await client.start(TOKEN)

if __name__ == "__main__":
    _lock = ensure_singleton()
    while True:
        try:
            logger.info("Starting Amber Bridge...")
            asyncio.run(start_bridge())
        except Exception as e:
            logger.error(f"Amber Bridge crashed: {e}. Retrying in 10s...")
            time.sleep(10)
