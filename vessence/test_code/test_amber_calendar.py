import discord
import asyncio
import os

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460

class AmberCalendarTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        print("Step 1: Asking Amber to check the calendar...")
        await channel.send("Amber, please go to calendar.google.com and tell me what you see today. Just a brief summary.")
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        print(f"Amber's response: {message.content}")
        if "calendar" in message.content.lower() or "schedule" in message.content.lower() or "today" in message.content.lower():
            print("SUCCESS: Amber responded to calendar command.")
            await self.close()
        elif "error" in message.content.lower() or "failed" in message.content.lower():
            print(f"FAILURE: Amber reported an error: {message.content}")
            await self.close()

async def main():
    intents = discord.Intents.all()
    client = AmberCalendarTester(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=180.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond to calendar command in time.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
