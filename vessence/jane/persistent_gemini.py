"""Compatibility shim — moved to llm_brain/v1/persistent_gemini.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_brain.v1.persistent_gemini import *  # noqa: F401,F403
