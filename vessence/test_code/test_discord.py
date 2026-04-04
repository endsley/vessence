import discord
import os
from dotenv import load_dotenv

# Ensure we're loading the .env from the my_agent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "my_agent", ".env"))
token = os.getenv('DISCORD_TOKEN')

print(f"DEBUG: Token starts with: {token[:10]}...")

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.close()

client = MyClient(intents=discord.Intents.default())
try:
    client.run(token)
except Exception as e:
    print(f"FATAL ERROR: {e}")
