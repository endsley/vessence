#!/bin/bash
# Claude Code PreToolUse hook — checks system load before Bash/Agent calls
# Output is injected into Jane's context so she adjusts concurrency accordingly
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/ambient/vessence/agent_skills/system_load.py --oneline 2>/dev/null
