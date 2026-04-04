import os
from google import genai
from dotenv import load_dotenv

load_dotenv("/home/chieh/vessence/.env")
api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})

print("Available models:")
for model in client.models.list():
    # Print name and actions
    print(f"Name: {model.name}, Actions: {model.supported_actions}")
