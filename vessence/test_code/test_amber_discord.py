import discord
import asyncio

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
AMBER_USER_ID = 1480768440267706460

class TestAmberClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        amber = await self.fetch_user(AMBER_USER_ID)
        if not amber:
            print(f"ERROR: Could not find Amber with ID {AMBER_USER_ID}")
            await self.close()
            return

        print(f"Sending test DM to Amber ({amber})...")
        await amber.send("Amber, please show me the picture of yourself.")
        print("Waiting for Amber's response...")

    async def on_message(self, message):
        # We only care about messages FROM Amber
        if message.author.id != AMBER_USER_ID:
            return

        # Print whatever she says
        print(f"\n[AMBER RESPONSE]:")
        print(f"Text: {message.content}")
        
        if message.attachments:
            for att in message.attachments:
                print(f"Attachment: {att.filename} ({att.size} bytes)")
            print("\nSUCCESS: Amber responded with an attachment!")
            await self.close()
        elif "amber.png" in message.content:
             print("\nFAILURE: Amber mentioned the file but did NOT attach it.")
             # We wait a bit more in case she sends it in a separate message,
             # though our bridge should send it immediately.
        else:
             print("\nSTATUS: Received intermediate text response.")

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    client = TestAmberClient(intents=intents)
    try:
        # Give her 60 seconds to respond
        await asyncio.wait_for(client.start(TOKEN), timeout=60.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond in time.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
