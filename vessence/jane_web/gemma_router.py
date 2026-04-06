"""Compatibility shim — moved to intent_classifier/v1/gemma_router.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from intent_classifier.v1.gemma_router import *  # noqa: F401,F403
