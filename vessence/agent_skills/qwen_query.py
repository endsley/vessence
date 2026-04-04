#!/usr/bin/env python3
import sys
import os
import ollama
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM

def check_ollama():
    try:
        # Verify Ollama service is reachable on localhost
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False

def query_qwen(prompt):
    if not check_ollama():
        print("CRITICAL ERROR: Local Ollama service is UNREACHABLE. Refusing to fall back to Gemini.")
        sys.exit(1)

    system_instr = (
        f"You are Jane, {os.environ.get('USER_NAME', 'the user')}'s technical expert and friend. "
        "You are acting as the local Qwen specialist. "
        "Provide expert technical assistance using your local knowledge."
    )
    try:
        response = ollama.chat(
            model=LOCAL_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_instr},
                {"role": "user", "content": prompt}
            ]
        )
        # Explicit header for transparency
        print("--- LOCAL QWEN RESPONSE (OLLAMA) ---")
        print(response['message']['content'])
    except Exception as e:
        print(f"Ollama Execution Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: qwen_query.py <prompt>")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    query_qwen(prompt)
