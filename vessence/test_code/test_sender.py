import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('/home/chieh/vessence/.env')
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))

class Sender(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}. Sending test message...")
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("Health Check: Can I speak?")
            print("Message sent successfully.")
        else:
            print(f"Could not find channel {CHANNEL_ID}")
        await self.close()

async def main():
    intents = discord.Intents.default()
    client = Sender(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
