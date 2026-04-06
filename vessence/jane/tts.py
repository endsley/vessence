"""Compatibility shim — moved to tts_engine/v1/edge_tts.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tts_engine.v1.edge_tts import *  # noqa
