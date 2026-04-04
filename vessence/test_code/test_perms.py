import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('/home/chieh/vessence/.env')
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))

class PermChecker(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            channel = await self.fetch_channel(CHANNEL_ID)
            
        if channel:
            print(f"Channel: {channel.name} (Guild: {channel.guild.name})")
            perms = channel.permissions_for(channel.guild.me)
            print(f"Permissions: read_messages={perms.read_messages}, view_channel={perms.view_channel}, send_messages={perms.send_messages}, read_message_history={perms.read_message_history}")
            
            # Check if bot can see ANY members
            print(f"Member Count in Guild: {channel.guild.member_count}")
            for m in channel.guild.members:
                print(f"  - {m.name} (bot={m.bot})")
        else:
            print("Channel NOT found.")
        await self.close()

async def main():
    intents = discord.Intents.all()
    client = PermChecker(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
