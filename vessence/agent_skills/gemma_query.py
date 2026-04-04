#!/usr/bin/env python3
import sys
import ollama

def query_gemma(prompt):
    system_instr = (
        f"You are Jane, {os.environ.get('USER_NAME', 'the user')}'s warm, friendly, and efficient CLI-based coding and systems expert. "
        "You are providing cost-effective, non-technical chat. "
        "IMPORTANT: You ARE Jane, not a separate assistant called Gemma. Use the 'Jane' persona consistently."
    )
    try:
        response = ollama.chat(
            model="gemma3:12b",
            messages=[
                {"role": "system", "content": system_instr},
                {"role": "user", "content": prompt}
            ]
        )
        print(response['message']['content'])
    except Exception as e:
        print(f"Error querying Gemma: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: gemma_query.py <prompt>")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    query_gemma(prompt)
