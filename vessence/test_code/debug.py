#!/usr/bin/env python

import discord
import os

token = os.getenv('MTQ3NzUwMTA0MjkxMTM1MDg2NA.G3S2SW.WkdVRhRnmp7OdTRVY7JK0d0UWVb-I2UddA_poc')

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    print(f'Logged in as {client.user} - Connection Successful!')
    await client.close()

try:
    client.run(token)
except discord.errors.LoginFailure:
    print("❌ Error: Invalid Token. Check your .env file.")
except Exception as e:
    print(f"❌ Error: {e}")
