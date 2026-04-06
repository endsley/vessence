"""Compatibility shim — moved to context_builder/v1/query_live_memory.py"""
import sys, os, runpy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from context_builder.v1.query_live_memory import *  # noqa: F401,F403
if __name__ == "__main__":
    sys.argv[0] = os.path.join(os.path.dirname(__file__), "..", "context_builder", "v1", "query_live_memory.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
