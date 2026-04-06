"""Compatibility shim — this module moved to agent_skills/memory/v1/add_forgettable_memory.py"""
import sys, os, runpy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Re-export for import compatibility
from agent_skills.memory.v1.add_forgettable_memory import *  # noqa: F401,F403
# Forward CLI execution to the real script
if __name__ == "__main__":
    sys.argv[0] = os.path.join(os.path.dirname(__file__), "memory", "v1", "add_forgettable_memory.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
