import discord
import asyncio
import io
import os

TOKEN = "MTQ4MTA4OTg2NjEwMzEzMjM1Mw.G0vlLa.L8VohW9eepJEvhrToyb6c3nJ8aJawcShGAtmuw"
CHANNEL_ID = 1476824260617048087
AMBER_ID = 1480768440267706460
AMBER_MENTION = f"<@{AMBER_ID}>"
VAULT_DIR = "/home/chieh/ambient/vault"

class AmberAgentTester(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Channel {CHANNEL_ID} not found.")
            await self.close()
            return

        # 1. Create and share the text file
        print("Step 1: Uploading agent description file to Amber...")
        content = "We have 3 agents running on this system: Amber, Katie, and Jane. Amber is the vault assistant, Katie is the tester, and Jane is the local CLI bridge."
        test_file = io.BytesIO(content.encode('utf-8'))
        await channel.send(f"{AMBER_MENTION} Please read, categorize, and store this agent info file named 'agent_info.txt'.", file=discord.File(test_file, filename="agent_info.txt"))
        
    async def on_message(self, message):
        if message.author.id != AMBER_ID:
            return

        # Check for step 1 completion (Amber acknowledged saving)
        if "agent_info.txt" in message.content.lower() and not hasattr(self, 'step2_done'):
            print(f"Amber Reply: {message.content}")
            
            # PHYSICAL CHECK
            target_path = os.path.join(VAULT_DIR, "agent_info.txt")
            if os.path.exists(target_path):
                print(f"SUCCESS: File physically exists at {target_path}")
            else:
                print(f"FAILURE: File DOES NOT exist at {target_path}")
                # We'll continue anyway to see if she can retrieve it from elsewhere
            
            self.step2_done = True
            
            # 2. Ask Amber about the contents
            print("\nStep 2: Asking Amber about the content of the file...")
            await message.channel.send(f"{AMBER_MENTION} Please call vault_send_file for 'agent_info.txt' and tell me the 3 agents listed in it.")
            return

        # Check for step 2 completion (the actual retrieval)
        if hasattr(self, 'step2_done'):
            print(f"\n[FINAL AMBER RESPONSE]:")
            print(f"Text: {message.content}")
            
            # Verify if she actually knows the content
            if all(name in message.content for name in ["Amber", "Katie", "Jane"]):
                print("\nCRITICAL SUCCESS: Amber correctly retrieved and identified the agent info!")
                await self.close()
            else:
                print("\nCRITICAL FAILURE: Amber did not correctly identify the agents from the file.")
                await self.close()

async def main():
    intents = discord.Intents.all()
    client = AmberAgentTester(intents=intents)
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=120.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Amber did not respond in time.")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
