import discord
import asyncio
import os

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460

class AmberVoiceTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        print("Step 1: Asking Amber to speak...")
        await channel.send("Amber, please say 'Hello, your voice system is working perfectly' out loud using your new voice.")
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        print(f"Amber's response: {message.content}")
        if message.attachments:
            for att in message.attachments:
                if att.filename.endswith(".wav"):
                    print(f"SUCCESS: Amber attached a voice message: {att.filename} ({att.size} bytes)")
                    await self.close()
                    return
        
        if "error" in message.content.lower() or "failed" in message.content.lower():
            print(f"FAILURE: Amber reported an error: {message.content}")
            await self.close()

async def main():
    intents = discord.Intents.all()
    client = AmberVoiceTester(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=90.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond with a voice file in time.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
