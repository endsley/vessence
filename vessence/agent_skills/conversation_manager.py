"""Compatibility shim — this module moved to agent_skills/memory/v1/conversation_manager.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent_skills.memory.v1.conversation_manager import *  # noqa: F401,F403
