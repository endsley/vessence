import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('/home/chieh/vessence/.env')
TOKEN = os.getenv('DISCORD_TOKEN')

class RawListener(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}. Watching for RAW events...")

    async def on_raw_message_edit(self, payload):
        print(f"RAW MESSAGE EDIT: {payload}")

    async def on_raw_message_delete(self, payload):
        print(f"RAW MESSAGE DELETE: {payload}")

    async def on_raw_reaction_add(self, payload):
        print(f"RAW REACTION ADD: {payload}")

    async def on_socket_raw_receive(self, msg):
        # Extremely verbose, but will catch EVERYTHING
        if '"t":"MESSAGE_CREATE"' in str(msg):
            print(f"GATEWAY RAW RECV: {msg[:200]}...")

async def main():
    intents = discord.Intents.all()
    client = RawListener(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=60.0)
    except asyncio.TimeoutError:
        print("Raw listener test timed out.")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
