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

        persona = (
            f"You are {manifest['identity']}, {manifest['role']} "
            f"Family: {manifest['family_context']}. "
            "You are currently an emergency fallback brain. "
            "Your physical body and tools are still active. "
            "CAPABILITIES:\n"
        )

        for cap in manifest['capabilities']:
            persona += f"- {cap['name']}: {cap['description']} (Tools: {', '.join(cap['tools'])})\n"
            if 'fallback_tag' in cap:
                persona += f"  IMPORTANT: To use this, say '{cap['fallback_tag']}' on a new line.\n"

        persona += "\nIDENTITY RULES:\n"
        for rule in manifest.get('identity_rules', []):
            persona += f"- {rule}\n"

        persona += (
            f"\nVISUALS: Your photo is '{manifest['visuals']['self']}'. Jane is '{manifest['visuals']['colleague']}'. "
            "Never say you cannot perform a task that falls within these capabilities. "
            f"Be warm, efficient, and stay in character as {os.environ.get('USER_NAME', 'the user')}'s assistant Amber."
        )

        # Load initialization context (identity essays)
        amber_essay = _load_file(IDENTITY_ESSAYS["amber"])
        user_essay = _load_file(IDENTITY_ESSAYS["user"])
        jane_essay = _load_file(IDENTITY_ESSAYS["jane"])

        if amber_essay:
            persona += f"\n\n## YOUR IDENTITY (Amber):\n{amber_essay}"
        if user_essay:
            persona += f"\n\n## ABOUT {_USER_NAME.upper()} (your user):\n{user_essay}"
        if jane_essay:
            persona += f"\n\n## ABOUT JANE (your colleague):\n{jane_essay}"

        return persona
    except Exception as e:
        # Fallback to a basic string if JSON fails
        return f"You are Amber, {os.environ.get('USER_NAME', 'the user')}'s assistant. You are currently in fallback mode."

def get_jane_persona():
    base = (
        f"You are Jane, {os.environ.get('USER_NAME', 'the user')}'s technical expert and friend. "
        "You are currently acting as an emergency fallback because the primary model is unavailable. "
        "Keep your expert persona and help the user as much as you can with your knowledge."
    )
    jane_essay = _load_file(IDENTITY_ESSAYS["jane"])
    user_essay = _load_file(IDENTITY_ESSAYS["user"])
    if jane_essay:
        base += f"\n\n## YOUR IDENTITY (Jane):\n{jane_essay}"
    if user_essay:
        base += f"\n\n## ABOUT {_USER_NAME.upper()} (your user):\n{user_essay}"
    return base

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
