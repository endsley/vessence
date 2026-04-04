# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import subprocess
import json
import logging
from google.adk.tools.base_tool import BaseTool
from pydantic import Field
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jane.config import ADK_VENV_PYTHON, RESEARCH_ASSISTANT_SCRIPT

logger = logging.getLogger('discord_agent.tools.research')

class TechnicalResearchTool(BaseTool):
    """
    A tool that uses local Qwen to perform deep technical analysis on search results.
    Provide a file path containing raw search data (e.g. from google_search) and it will find a solution.
    """
    def __init__(self):
        super().__init__(
            name="technical_research_analysis",
            description="Analyzes raw technical search data using local Qwen to find a specific fix/cause."
        )

    async def __call__(self, raw_data_path: str) -> str:
        if not os.path.exists(raw_data_path):
            return f"Error: Data file {raw_data_path} not found."

        output_path = raw_data_path + ".analysis.json"
        
        try:
            cmd = [ADK_VENV_PYTHON, RESEARCH_ASSISTANT_SCRIPT, raw_data_path, output_path]
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
            
            # The script prints the JSON result
            analysis = json.loads(result)
            if "error" in analysis:
                return f"Research failed: {analysis['error']}"
            
            return (
                f"### Technical Research Result\n"
                f"**Cause:** {analysis.get('cause', 'Unknown')}\n"
                f"**Fix:** {analysis.get('fix', 'No fix found')}\n"
                f"**Source:** {analysis.get('source_url', 'N/A')}"
            )
        except Exception as e:
            return f"Error running research assistant: {str(e)}"
