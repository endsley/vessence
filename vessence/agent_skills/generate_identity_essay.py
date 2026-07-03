#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import chromadb
from google.genai import Client
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import get_chroma_client, ENV_FILE_PATH, VAULT_DIR, VECTOR_DB_USER_MEMORIES
from agent_skills.identity_essay_prompts import (
    amber_identity_prompt as _amber_identity_prompt,
    jane_identity_prompt as _jane_identity_prompt,
    memories_text_from_documents as _memories_text_from_documents,
    user_identity_prompt as _user_identity_prompt,
)

DB_PATH = VECTOR_DB_USER_MEMORIES
_USER_NAME = os.environ.get("USER_NAME", "user")
ESSAY_PATH = os.path.join(VAULT_DIR, "documents", f"{_USER_NAME}_identity_essay.txt")
JANE_ESSAY_PATH = os.path.join(VAULT_DIR, "documents", "jane_identity_essay.txt")
AMBER_ESSAY_PATH = os.path.join(VAULT_DIR, "documents", "amber_identity_essay.txt")

load_dotenv(ENV_FILE_PATH)

def update_essay():
    client = get_chroma_client(path=DB_PATH)
    try:
        collection = client.get_collection(name="user_memories")
        all_mems = collection.get(include=["documents"])
        documents = all_mems.get("documents", [])
    except Exception as e:
        print(f"Could not load memories: {e}")
        documents = []

    # 1. Read existing essays
    old_essay = ""
    if os.path.exists(ESSAY_PATH):
        with open(ESSAY_PATH, "r") as f:
            old_essay = f.read()

    jane_old_essay = ""
    if os.path.exists(JANE_ESSAY_PATH):
        with open(JANE_ESSAY_PATH, "r") as f:
            jane_old_essay = f.read()

    amber_old_essay = ""
    if os.path.exists(AMBER_ESSAY_PATH):
        with open(AMBER_ESSAY_PATH, "r") as f:
            amber_old_essay = f.read()

    genai_client = Client(api_key=os.getenv('GOOGLE_API_KEY'))
    # Truncate memories to avoid exceeding context window (~150k chars ~ 40k tokens)
    memories_text = _memories_text_from_documents(documents)

    # --- Generate User Identity Essay (Shared Understanding) ---
    prompt_chieh = _user_identity_prompt(old_essay, memories_text)

    print("Generating user identity essay...")
    try:
        response_chieh = genai_client.models.generate_content(model="gemini-2.5-pro", contents=prompt_chieh)
        if response_chieh.text:
            os.makedirs(os.path.dirname(ESSAY_PATH), exist_ok=True)
            with open(ESSAY_PATH, "w") as f:
                f.write(response_chieh.text)
            print("User essay updated.")
        else:
            print("Warning: user essay response was empty, skipping write.")
    except Exception as e:
        print(f"Error generating user essay: {e}")

    # --- Generate Jane's Self-Reflection Essay ---
    prompt_jane = _jane_identity_prompt(jane_old_essay, memories_text)

    print("Generating Jane's identity essay...")
    try:
        response_jane = genai_client.models.generate_content(model="gemini-2.5-pro", contents=prompt_jane)
        if response_jane.text:
            with open(JANE_ESSAY_PATH, "w") as f:
                f.write(response_jane.text)
            print("Jane's essay updated.")
        else:
            print("Warning: Jane's essay response was empty, skipping write.")
    except Exception as e:
        print(f"Error generating Jane's essay: {e}")

    # --- Generate Amber's Self-Reflection Essay ---
    prompt_amber = _amber_identity_prompt(amber_old_essay, memories_text)

    print("Generating Amber's identity essay...")
    try:
        response_amber = genai_client.models.generate_content(model="gemini-2.5-pro", contents=prompt_amber)
        if response_amber.text:
            with open(AMBER_ESSAY_PATH, "w") as f:
                f.write(response_amber.text)
            print("Amber's essay updated.")
        else:
            print("Warning: Amber's essay response was empty, skipping write.")
    except Exception as e:
        print(f"Error generating Amber's essay: {e}")

    print("Identity essay update complete.")

if __name__ == "__main__":
    update_essay()
