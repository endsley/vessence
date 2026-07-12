#!/usr/bin/env python3
import os
import json
import logging
from pathlib import Path
from google.genai import Client
from dotenv import load_dotenv
import time

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills.model_update_helpers import (
    MODEL_UPDATE_SEARCH_QUERY,
    model_update_prompt as _model_update_prompt,
    should_persist_model_update as _should_persist_model_update,
)
from jane.config import ENV_FILE_PATH, PENDING_UPDATES_PATH

from agent_skills.cron_token_meter import log_llm_call as _log_llm_call

NOTIFY_FILE = PENDING_UPDATES_PATH
load_dotenv(ENV_FILE_PATH)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model_watcher")

# Our current peak model
CURRENT_MODEL = "gemini-2.5-pro"

def check_for_new_models():
    genai_client = Client(api_key=os.getenv('GOOGLE_API_KEY'))
    
    search_query = MODEL_UPDATE_SEARCH_QUERY
    logger.info(f"Searching for: {search_query}")
    
    # We use Gemini to perform the search and analysis in one go
    prompt = _model_update_prompt(CURRENT_MODEL)
    start = time.perf_counter()

    try:
        response = None
        # Use AFC to get search results and analyze
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        data = json.loads(response.text)
        
        if _should_persist_model_update(data):
            logger.info(f"New model detected: {data['model_name']}")
            os.makedirs(os.path.dirname(NOTIFY_FILE), exist_ok=True)
            with open(NOTIFY_FILE, "w") as f:
                json.dump(data, f)
        else:
            logger.info("No new models found.")

        _log_llm_call(
            provider="gemini",
            model="gemini-2.5-flash",
            prompt_chars=len(prompt),
            response_chars=len(response.text or ""),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            success=True,
            phase="check_for_updates",
            job=os.environ.get("CRON_JOB"),
        )
    except Exception as e:
        _log_llm_call(
            provider="gemini",
            model="gemini-2.5-flash",
            prompt_chars=len(prompt),
            response_chars=0,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            success=False,
            phase="check_for_updates",
            job=os.environ.get("CRON_JOB"),
            error=str(e),
        )
        logger.error(f"Failed to check for updates: {e}")

if __name__ == "__main__":
    check_for_new_models()
