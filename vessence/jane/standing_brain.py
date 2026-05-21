"""Compatibility shim — moved to llm_brain/v1/standing_brain.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_brain.v1.standing_brain import *  # noqa: F401,F403
from llm_brain.v1.standing_brain import _configured_provider  # noqa: F401
