#!/usr/bin/env python3
import sys
import json
import ollama
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.research_result_helpers import (
    analyzer_error_result as _analyzer_error_result,
    analyzer_missing_file_result as _analyzer_missing_file_result,
    analyzer_result_from_model_content as _analyzer_result_from_model_content,
)
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM

def analyze_search_results(file_path):
    if not os.path.exists(file_path):
        return _analyzer_missing_file_result()

    with open(file_path, 'r') as file:
        search_results = file.read()

    system_instr = (
        "You are a Technical Research Analyzer. Your goal is to find a high-confidence solution "
        "to a technical problem from raw search results.\n"
        "Requirements:\n"
        "1. Extract the Cause (Why it happens).\n"
        "2. Extract the Fix (Code or specific action).\n"
        "3. Extract the Source (The URL).\n"
        "4. ONLY provide a solution if you have HIGH CONFIDENCE. Otherwise, respond with 'NO_SOLUTION_FOUND'.\n"
        "5. Output MUST be a JSON object with keys: 'confidence', 'cause', 'fix', 'source', 'found'."
    )

    try:
        response = ollama.chat(
            model=LOCAL_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_instr},
                {"role": "user", "content": f"Analyze these search results:\n\n{search_results}"}
            ],
            format="json"
        )
        
        content = response['message']['content'].strip()
        return _analyzer_result_from_model_content(content)
    except Exception as e:
        return _analyzer_error_result(e)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path provided"}, indent=4))
        sys.exit(1)

    file_path = sys.argv[1]
    result = analyze_search_results(file_path)
    print(json.dumps(result, indent=4))
