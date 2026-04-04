import os
from google import genai
from dotenv import load_dotenv

load_dotenv("/home/chieh/vessence/.env")
api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})

print("Available models:")
try:
    for model in client.models.list():
        print(f"{model.name}")
except Exception as e:
    print(f"Error: {e}")
