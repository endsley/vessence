import discord
import asyncio
import os
from dotenv import load_dotenv

TOKEN = "MTQ4MDkyMTg3NzE3NzE3MjA2OQ.GudM61.fHnesOW3FK3r1onHC1mddqtBS8xrQyvUunKHAQ"
CHANNEL_ID = 1476824260617048087

class Checker(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}. Checking channel {CHANNEL_ID}...")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            channel = await self.fetch_channel(CHANNEL_ID)
            
        if channel:
            print(f"Channel found: {channel.name}")
            print("Fetching history...")
            async for message in channel.history(limit=5):
                print(f"RECENT MSG: author={message.author}, content='{message.content}'")
        else:
            print("Channel NOT found.")
        await self.close()

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    client = Checker(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
