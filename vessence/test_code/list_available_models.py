from google.genai import Client
import os
from dotenv import load_dotenv

load_dotenv('/home/chieh/vessence/.env')
client = Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Available Models:")
for m in client.models.list():
    print(f"- {m.name}")
