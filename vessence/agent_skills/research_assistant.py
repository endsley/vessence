#!/usr/bin/env python3
import sys
import os
import json
import ollama
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM

def analyze_research(raw_data_path, output_path):
    """
    Uses local Qwen to digest raw web search data and produce a cited technical note.
    """
    if not os.path.exists(raw_data_path):
        return {"error": "Raw data file not found."}

    with open(raw_data_path, 'r') as f:
        raw_content = f.read()

    system_prompt = (
        "You are a Senior Technical Researcher. Analyze the provided raw web search data to find a solution to the user's problem.\n"
        "Rules:\n"
        "1. Provide a HIGH-CONFIDENCE technical note.\n"
        "2. If the data is conflicting, prioritize the most recent or official documentation.\n"
        "3. Format your output as a valid JSON object with: 'cause', 'fix', and 'source_url'.\n"
        "4. If no clear solution is found, return {'error': 'NO_SOLUTION_FOUND'}.\n"
        "Response MUST be valid JSON only."
    )

    try:
        response = ollama.chat(
            model=LOCAL_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"RAW SEARCH DATA:\n{raw_content[:15000]}"} # Limit input to fit local context
            ]
        )
        
        # Extract and parse JSON
        text = response['message']['content']
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        analysis = json.loads(text.strip())
        
        # Save the technical note to the research vault
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)
            
        return analysis

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: research_assistant.py <raw_data_path> <output_path>")
        sys.exit(1)
    
    result = analyze_research(sys.argv[1], sys.argv[2])
    print(json.dumps(result))
