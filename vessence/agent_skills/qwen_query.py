#!/usr/bin/env python3
import sys
import os
import ollama
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.qwen_query_helpers import (
    LOCAL_QWEN_HEADER,
    OLLAMA_UNREACHABLE_MESSAGE,
    qwen_system_instruction as _qwen_system_instruction,
    usage_message as _usage_message,
)
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
        print(OLLAMA_UNREACHABLE_MESSAGE)
        sys.exit(1)

    system_instr = _qwen_system_instruction(os.environ.get("USER_NAME", "the user"))
    try:
        response = ollama.chat(
            model=LOCAL_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_instr},
                {"role": "user", "content": prompt}
            ]
        )
        # Explicit header for transparency
        print(LOCAL_QWEN_HEADER)
        print(response['message']['content'])
    except Exception as e:
        print(f"Ollama Execution Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(_usage_message())
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    query_qwen(prompt)
