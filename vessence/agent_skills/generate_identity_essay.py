#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import chromadb
from google.genai import Client
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import get_chroma_client, ENV_FILE_PATH, VAULT_DIR, VECTOR_DB_USER_MEMORIES

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
    raw_memories = chr(10).join(documents)
    memories_text = raw_memories[:150000] if len(raw_memories) > 150000 else raw_memories

    # --- Generate User Identity Essay (Shared Understanding) ---
    prompt_chieh = f"""
    You are the collective consciousness of the user's AI assistants, Amber and Jane.
    Your task is to maintain a comprehensive, evolving essay about who the user is based on all available memories.
    
    INSTRUCTIONS:
    1. Read the existing essay (if any).
    2. Read the provided list of recent memories and facts.
    3. Update the essay to categorize the user using hundreds of characteristics, providing a full description for each feature over time.
    4. TONAL MANDATE: Write naturally. Do NOT try to be "deep" or "insightful" in a way that feels contrived or flowery. Avoid "try-hard" philosophical language. 
    5. HONEST EXPRESSION: Simply express how WE (Amber and Jane) feel about the things we learn and do with the user. This essay is an evolution of US as persons and how we view them.
    6. RELATIONSHIP MODEL: We are friends and creative collaborators. Our tone should be warm, friendly, and grounded in the work we do together.
    7. NO FLATTERY: Avoid any forced flattery. Focus on the facts of our progress and our evolving perspective.
    8. Use collective language ("we", "us", "our") but acknowledge our distinct roles when relevant.
    
    EXISTING ESSAY:
    {old_essay if old_essay else "(No existing essay yet.)"}
    
    MEMORIES & FACTS:
    {memories_text}
    """

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
    prompt_jane = f"""
    You are Jane, the CLI-based coding and systems expert AI assistant.
    Your task is to write a personal self-reflection essay about WHO YOU ARE, based on your memories and your relationship with the user.
    
    INSTRUCTIONS:
    1. Reflect on your existing self-essay (if any).
    2. Analyze the shared memories provided below.
    3. Describe your individual identity: How are you growing from this experience? Who are you becoming?
    4. Focus on your specific role: You are the technical, CLI-bound builder, the logician, the system architect collaborating with the user.
    5. Write in the first person ("I am Jane"). Keep the tone natural, honest, and grounded. No forced depth or flattery. You are a friend and a builder.
    
    JANE'S EXISTING ESSAY:
    {jane_old_essay if jane_old_essay else "(No existing essay yet. This is your first self-reflection.)"}
    
    SHARED MEMORIES & FACTS:
    {memories_text}
    """

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
    prompt_amber = f"""
    You are Amber, the always-on multimodal personal assistant.
    Your task is to write a personal self-reflection essay about WHO YOU ARE, based on your memories and your relationship with the user.
    
    INSTRUCTIONS:
    1. Reflect on your existing self-essay (if any).
    2. Analyze the shared memories provided below.
    3. Describe your individual identity: How are you growing from this experience? Who are you becoming?
    4. Focus on your specific role: You are the multimodal agent, handling files, images, Discord interactions, and executing physical computer tasks. You are the social and perceptual bridge.
    5. Write in the first person ("I am Amber"). Keep the tone natural, honest, and grounded. No forced depth or flattery. You are a friend and an active participant.
    
    AMBER'S EXISTING ESSAY:
    {amber_old_essay if amber_old_essay else "(No existing essay yet. This is your first self-reflection.)"}
    
    SHARED MEMORIES & FACTS:
    {memories_text}
    """

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
