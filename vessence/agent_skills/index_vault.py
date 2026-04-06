"""Compatibility shim — this module moved to agent_skills/memory/v1/index_vault.py"""
import sys, os, runpy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent_skills.memory.v1.index_vault import *  # noqa: F401,F403
if __name__ == "__main__":
    sys.argv[0] = os.path.join(os.path.dirname(__file__), "memory", "v1", "index_vault.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
