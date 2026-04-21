"""Compatibility shim — moved to context_builder/v1/claude_smart_context.py"""
import sys, os
# Use realpath to follow symlinks — this file is called via .claude/hooks/context_build.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from context_builder.v1.claude_smart_context import *  # noqa: F401,F403

if __name__ == "__main__":
    from context_builder.v1.claude_smart_context import main
    raise SystemExit(main())
