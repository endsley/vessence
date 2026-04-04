import os
from google import genai
from dotenv import load_dotenv

load_dotenv("/home/chieh/vessence/.env")
api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello, how are you?"
)
print(response.text)
