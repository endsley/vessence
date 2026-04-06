"""Compatibility shim — moved to context_builder/v1/context_builder.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from context_builder.v1.context_builder import *  # noqa: F401,F403
