import discord
import asyncio
import io

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460

class AmberTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        # 1. Send a test file to Amber
        print("Step 1: Sending test image to Amber...")
        test_file = io.BytesIO(b"test data for image")
        await channel.send("Amber, please save this test image of a cat.", file=discord.File(test_file, filename="test_cat.png"))
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        # Check for step 1 completion
        if "test_cat.png" in message.content.lower() and not hasattr(self, 'step2_done'):
            print(f"SUCCESS: Amber acknowledged saving the file: {message.content}")
            self.step2_done = True
            
            # 2. Ask to retrieve it
            print("\nStep 2: Asking Amber to retrieve the image...")
            await message.channel.send("Amber, please show me the test_cat.png you just saved.")
            return

        # Check for step 2 completion (the actual attachment)
        if hasattr(self, 'step2_done'):
            print(f"\n[FINAL AMBER RESPONSE]:")
            print(f"Text: {message.content}")
            if message.attachments:
                for att in message.attachments:
                    print(f"Attachment: {att.filename} ({att.size} bytes)")
                print("\nCRITICAL SUCCESS: Amber attached the image!")
                await self.close()
            elif "test_cat.png" in message.content:
                print("\nCRITICAL FAILURE: Amber mentioned the file but did NOT attach it.")
                await self.close()

async def main():
    intents = discord.Intents.all()
    client = AmberTester(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=90.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond in time.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
