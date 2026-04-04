# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import logging
import json
import os
import sys
from pathlib import Path
from google.genai import types
from google.adk.models.registry import LLMRegistry
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
from jane.config import ADD_FACT_SCRIPT, ADK_VENV_PYTHON

logger = logging.getLogger('discord_agent.logic')

ANALYZER_MODEL = os.getenv("AMBER_BRAIN_MODEL", "gemini")
if ANALYZER_MODEL in ["qwen", "qwen-local"]:
    ANALYZER_MODEL = LOCAL_LLM_MODEL_LITELLM
elif ANALYZER_MODEL == "deepseek":
    ANALYZER_MODEL = "deepseek/deepseek-chat"
else:
    ANALYZER_MODEL = "gemini-2.5-flash"

FACT_EXTRACTION_PROMPT = """
You are a memory analyst. Your task is to extract permanent facts from the given conversation snippet.
A fact is a piece of information about the user, their preferences, their life, or their vault files that should be remembered long-term.

For each fact, categorize it into a high-level 'topic' and a more specific 'subtopic'.
Examples of Topics: "Family", "Work", "Preferences", "Technical", "Health", "Identity", "Vault".

Conversation:
{conversation}

Output format:
JSON list of objects.
[
  {{"fact": "Example: user prefers a certain drink.", "topic": "Preferences", "subtopic": "Drinks"}},
  {{"fact": "Example: user has a family member.", "topic": "Family", "subtopic": "Children"}}
]
If no facts, output: []
"""

async def detect_facts_and_contradictions(callback_context, llm_response=None):
    """
    Callback to analyze model response for new facts or conflicts.
    Uses ADK Context methods for memory.
    """
    try:
        user_id = callback_context.user_id
        # Safety check for session
        if not callback_context.session or not callback_context.session.events:
            return None

        from google.adk.models.google_llm import Gemini
        from google.adk.models.lite_llm import LiteLlm
        
        if ANALYZER_MODEL.startswith("ollama/"):
            model = LiteLlm(model=ANALYZER_MODEL, api_base="http://localhost:11434")
        else:
            model = Gemini(model=ANALYZER_MODEL)
        
        # 1. Get the user input from session history
        events = callback_context.session.events
        last_user_msg = ""
        for e in reversed(events):
            if e.author == "user" and e.content and e.content.parts:
                for part in e.content.parts:
                    if part.text:
                        last_user_msg = part.text
                        break
                if last_user_msg:
                    break
        
        if not last_user_msg:
            return None

        # 2. Extract facts using the analyzer model
        prompt = FACT_EXTRACTION_PROMPT.format(conversation=last_user_msg)
        
        try:
            from google.adk.models.llm_request import LlmRequest
            llm_request = LlmRequest(contents=[types.Content(parts=[types.Part(text=prompt)], role="user")])
            
            text = ""
            async for response in model.generate_content_async(llm_request=llm_request):
                if response.content and response.content.parts:
                    part_text = response.content.parts[0].text
                    if part_text:
                        text += part_text
            
            # Clean JSON string
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            fact_objects = json.loads(text.strip())
        except Exception as e:
            logger.warning(f"Fact extraction failed: {e}")
            return None

        if not fact_objects:
            return None

        # 3. For each fact object, save with metadata
        for obj in fact_objects:
            fact = obj.get("fact")
            topic = obj.get("topic", "General")
            subtopic = obj.get("subtopic", "General")
            
            if not fact:
                continue

            # 4. Save fact directly to ChromaDB via add_fact.py
            try:
                import subprocess
                cmd = [
                    ADK_VENV_PYTHON,
                    ADD_FACT_SCRIPT,
                    fact, "--topic", topic, "--subtopic", subtopic, "--author", "amber"
                ]
                subprocess.run(cmd, capture_output=True, timeout=30)
                logger.info(f"Layered Memory Saved: [{topic}/{subtopic}] {fact}")
            except Exception as e:
                logger.error(f"Failed to save fact: {e}")

    except Exception as e:
        logger.error(f"Error in fact detection: {e}")
        
    return None
