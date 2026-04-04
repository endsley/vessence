import os
from dotenv import load_dotenv
load_dotenv("/home/chieh/vessence/.env")
import discord
import asyncio
import sys

TOKEN = os.getenv("DISCORD_TOKEN")

class Listener(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}. Waiting for messages in ANY channel...")

    async def on_message(self, message):
        print(f"MESSAGE RECEIVED: author={message.author}, channel={message.channel}, content='{message.content}'")

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    intents.messages = True
    client = Listener(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=30.0)
    except asyncio.TimeoutError:
        print("Test timed out.")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
