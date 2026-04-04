#!/usr/bin/env python3
import os
import json
import logging
from pathlib import Path
from google.genai import Client
from dotenv import load_dotenv

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import ENV_FILE_PATH, PENDING_UPDATES_PATH

NOTIFY_FILE = PENDING_UPDATES_PATH
load_dotenv(ENV_FILE_PATH)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model_watcher")

# Our current peak model
CURRENT_MODEL = "gemini-2.5-pro"

def check_for_new_models():
    genai_client = Client(api_key=os.getenv('GOOGLE_API_KEY'))
    
    search_query = "latest Google Gemini model announcement news for developers coding"
    logger.info(f"Searching for: {search_query}")
    
    # We use Gemini to perform the search and analysis in one go
    prompt = f"""
    Search the internet for the latest Google Gemini AI models. 
    Our current highest-tier model is {CURRENT_MODEL}.
    
    Is there a newer or more capable version available (e.g., Gemini 3.0, or a new ultra/pro variant with better coding capabilities)?
    
    Return a JSON object:
    {{
      "new_model_found": true/false,
      "model_name": "name of the new model",
      "key_improvements": "bullet points of key features",
      "source_url": "link to news"
    }}
    
    Only set new_model_found to true if the model is genuinely newer or significantly upgraded compared to {CURRENT_MODEL}.
    """

    try:
        # Use AFC to get search results and analyze
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        data = json.loads(response.text)
        
        if data.get("new_model_found"):
            logger.info(f"New model detected: {data['model_name']}")
            os.makedirs(os.path.dirname(NOTIFY_FILE), exist_ok=True)
            with open(NOTIFY_FILE, "w") as f:
                json.dump(data, f)
        else:
            logger.info("No new models found.")
            
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")

if __name__ == "__main__":
    check_for_new_models()
