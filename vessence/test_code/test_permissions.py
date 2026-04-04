import discord
import asyncio

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087

class PermissionTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Cannot find channel {CHANNEL_ID}")
            await self.close()
            return

        perms = channel.permissions_for(channel.guild.me)
        print(f"Permissions for {self.user} in #{channel.name}:")
        print(f"  - View Channel: {perms.view_channel}")
        print(f"  - Send Messages: {perms.send_messages}")
        print(f"  - Read Message History: {perms.read_message_history}")
        print(f"  - Use External Emojis: {perms.use_external_emojis}")
        
        await self.close()

async def main():
    intents = discord.Intents.default()
    intents.guilds = True
    client = PermissionTester(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
