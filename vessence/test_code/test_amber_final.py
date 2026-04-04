import discord
import asyncio
import os

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460
AMBER_MENTION = f"<@{AMBER_ID}>"
IMAGE_PATH = "/home/chieh/Downloads/amber.png"
VAULT_DIR = "/home/chieh/ambient/vault"

class AmberFinalTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        # 1. Upload Amber's picture
        print(f"Step 1: Uploading {IMAGE_PATH} to Amber...")
        with open(IMAGE_PATH, "rb") as f:
            await channel.send(f"{AMBER_MENTION} Amber, please save this picture of yourself to your vault.", file=discord.File(f, filename="amber.png"))
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        # Check for step 1 acknowledgement
        if "amber.png" in message.content.lower() and not hasattr(self, 'step2_done'):
            print(f"Amber Reply: {message.content}")
            
            # PHYSICAL VERIFICATION
            target_path = os.path.join(VAULT_DIR, "amber.png")
            if os.path.exists(target_path):
                print(f"SUCCESS: amber.png physically exists at {target_path}")
            else:
                print(f"FAILURE: amber.png DOES NOT exist at {target_path}")
            
            self.step2_done = True
            
            # 2. Ask Amber to send it back
            print("\nStep 2: Asking Amber to retrieve and attach the picture...")
            await message.channel.send(f"{AMBER_MENTION} Amber, please retrieve and attach your picture (amber.png) and send it back to me.")
            return

        # Check for step 2 completion (the actual attachment)
        if hasattr(self, 'step2_done'):
            print(f"\n[FINAL AMBER RESPONSE]:")
            print(f"Text: {message.content}")
            if message.attachments:
                for att in message.attachments:
                    print(f"Attachment: {att.filename} ({att.size} bytes)")
                print("\nULTIMATE SUCCESS: Amber attached the image!")
                await self.close()
            elif "amber.png" in message.content:
                print("\nFAILURE: Amber mentioned the file but did NOT attach it.")
                # We stay open a bit longer to see if it comes in another message
            else:
                print(f"Received text: {message.content}")

async def main():
    intents = discord.Intents.all()
    client = AmberFinalTester(intents=intents)
    try:
        # Long timeout for model thinking and large file transfer
        await asyncio.wait_for(client.start(TOKEN), timeout=300.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
