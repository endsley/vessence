#!/usr/bin/env python3
import os
import sys
import json
import requests
import ollama
import argparse
from pathlib import Path
from dotenv import load_dotenv

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT))

from jane.config import (
    AMBER_ESSAY,
    USER_ESSAY,
    ENV_FILE_PATH,
    JANE_ESSAY,
    LOCAL_LLM_MODEL,
)
from agent_skills.fallback_personas import (
    amber_fallback_persona as _amber_fallback_persona,
    build_amber_persona as _build_amber_persona,
    build_jane_persona as _build_jane_persona,
)

load_dotenv(ENV_FILE_PATH)

CAPABILITIES_PATH = str(CODE_ROOT / "configs" / "amber_capabilities.json")
_USER_NAME = os.environ.get("USER_NAME", "user")
IDENTITY_ESSAYS = {
    "amber": AMBER_ESSAY,
    "user": USER_ESSAY,
    "jane": JANE_ESSAY,
}

def _load_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

def get_amber_persona():
    try:
        with open(CAPABILITIES_PATH, "r") as f:
            manifest = json.load(f)

        # Load initialization context (identity essays)
        amber_essay = _load_file(IDENTITY_ESSAYS["amber"])
        user_essay = _load_file(IDENTITY_ESSAYS["user"])
        jane_essay = _load_file(IDENTITY_ESSAYS["jane"])

        return _build_amber_persona(
            manifest,
            user_name=os.environ.get("USER_NAME", "the user"),
            essay_user_name=_USER_NAME,
            amber_essay=amber_essay,
            user_essay=user_essay,
            jane_essay=jane_essay,
        )
    except Exception as e:
        # Fallback to a basic string if JSON fails
        return _amber_fallback_persona(os.environ.get("USER_NAME", "the user"))

def get_jane_persona():
    jane_essay = _load_file(IDENTITY_ESSAYS["jane"])
    user_essay = _load_file(IDENTITY_ESSAYS["user"])
    return _build_jane_persona(
        user_name=os.environ.get("USER_NAME", "the user"),
        essay_user_name=_USER_NAME,
        jane_essay=jane_essay,
        user_essay=user_essay,
    )

PERSONAS = {
    "jane": get_jane_persona(),
    "amber": get_amber_persona()
}

def query_deepseek(prompt, system_instr):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DeepSeek key missing")
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instr},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']

def query_openai(prompt, system_instr):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI key missing")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_instr},
            {"role": "user", "content": prompt}
        ]
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']

def query_deepseek_local(prompt, system_instr):
    response = ollama.chat(
        model=LOCAL_LLM_MODEL,
        messages=[
            {"role": "system", "content": system_instr},
            {"role": "user", "content": prompt}
        ]
    )
    return response['message']['content']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="The user prompt")
    parser.add_argument("--identity", choices=["jane", "amber"], default="jane", help="Identity to use")
    args = parser.parse_args()

    system_instr = PERSONAS.get(args.identity)
    
    # Tier 1: DeepSeek API
    try:
        res = query_deepseek(args.prompt, system_instr)
        print(f"⚠️ Claude is unavailable. Responding via DeepSeek API.\n\n{res}")
        return
    except Exception as e:
        print(f"DeepSeek API failed: {e}", file=sys.stderr)

    # Tier 2: Local DeepSeek-R1
    try:
        res = query_deepseek_local(args.prompt, system_instr)
        print(f"⚠️ Claude is unavailable. Responding via local DeepSeek-R1:32b.\n\n{res}")
        return
    except Exception as e:
        print(f"Local DeepSeek-R1 failed: {e}", file=sys.stderr)

    # Tier 3: OpenAI
    try:
        res = query_openai(args.prompt, system_instr)
        print(f"⚠️ Claude is unavailable. Responding via OpenAI GPT-4o.\n\n{res}")
        return
    except Exception as e:
        print(f"OpenAI failed: {e}", file=sys.stderr)
        print("⚠️ All fallback providers failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
