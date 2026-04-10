"""Compatibility shim — moved to llm_brain/v1/brain_adapters.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_brain.v1.brain_adapters import *  # noqa: F401,F403
from llm_brain.v1.brain_adapters import _execute_subprocess_streaming  # noqa: F401
