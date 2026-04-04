import discord
import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('/home/chieh/vessence/.env')
TOKEN = os.getenv('DISCORD_TOKEN')

class DiscoveryClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("\nGuilds and Channels visible to this token:\n")
        
        if not self.guilds:
            print("NO GUILDS VISIBLE. The bot is likely not invited to any servers.")
        
        for guild in self.guilds:
            print(f"Guild: {guild.name} (ID: {guild.id})")
            for channel in guild.text_channels:
                perms = channel.permissions_for(guild.me)
                print(f"  - Channel: {channel.name} (ID: {channel.id}) | Read Msgs: {perms.read_messages} | History: {perms.read_message_history}")
        
        await self.close()

async def main():
    intents = discord.Intents.default()
    intents.guilds = True
    client = DiscoveryClient(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
