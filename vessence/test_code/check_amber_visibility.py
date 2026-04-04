import discord
import asyncio

TOKEN = "MTQ4MDc2ODQ0MDI2NzcwNjQ2MA.GcjBWg.kTlRl1VL0yiTKdKB3mbGZ7Z10YrljwHQCegC8Y"

class VisibilityClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("\nGuilds and Channels visible to Amber:")
        for guild in self.guilds:
            print(f"\nGuild: {guild.name} (ID: {guild.id})")
            for channel in guild.text_channels:
                print(f"  - Channel: {channel.name} (ID: {channel.id})")
        await self.close()

async def main():
    intents = discord.Intents.default()
    intents.guilds = True
    client = VisibilityClient(intents=intents)
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
