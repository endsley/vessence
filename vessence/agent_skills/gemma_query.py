#!/usr/bin/env python3
import os
import sys
import ollama

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from jane_web.jane_v2.models import STAGE2_MODEL
except Exception:
    STAGE2_MODEL = (
        os.environ.get("JANE_LOCAL_LLM")
        or os.environ.get("JANE_STAGE2_MODEL")
    )
    if not STAGE2_MODEL:
        raise RuntimeError(
            "Cannot resolve local LLM: jane_web.jane_v2.models import failed "
            "AND no JANE_LOCAL_LLM / JANE_STAGE2_MODEL env var is set"
        )


def query_local_llm(prompt):
    system_instr = (
        f"You are Jane, {os.environ.get('USER_NAME', 'the user')}'s warm, friendly, and efficient CLI-based coding and systems expert. "
        "You are providing cost-effective, non-technical chat. "
        "IMPORTANT: You ARE Jane, not a separate assistant called Gemma. Use the 'Jane' persona consistently."
    )
    try:
        response = ollama.chat(
            model=STAGE2_MODEL,
            messages=[
                {"role": "system", "content": system_instr},
                {"role": "user", "content": prompt}
            ],
            keep_alive=-1,
        )
        print(response['message']['content'])
    except Exception as e:
        print(f"Error querying local LLM: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: gemma_query.py <prompt>")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    query_local_llm(prompt)
