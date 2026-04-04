import discord
import asyncio
import io
import os

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460

class AmberPDFTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        # 1. Send a test PDF to Amber
        print("Step 1: Sending test PDF to Amber...")
        # Create a dummy PDF content
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        await channel.send("Amber, please save this research paper about AI.", file=discord.File(io.BytesIO(pdf_content), filename="ai_research.pdf"))
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        print(f"Amber's response: {message.content}")
        if "ai_research" in message.content.lower() and ("saved" in message.content.lower() or "successfully" in message.content.lower()):
            print("SUCCESS: Amber acknowledged saving the PDF.")
            await self.close()
        elif "error" in message.content.lower() or "failed" in message.content.lower():
            print(f"FAILURE: Amber reported an error: {message.content}")
            await self.close()

async def main():
    intents = discord.Intents.all()
    client = AmberPDFTester(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=60.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond in time.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
