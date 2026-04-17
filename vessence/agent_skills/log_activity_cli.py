#!/usr/bin/env python3
'''
log_activity_cli.py - Command-line wrapper for work_log_tools.log_activity.
'''
import argparse
import os
import sys
from pathlib import Path

# Ensure work_log_tools can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from work_log_tools import log_activity
except ImportError:
    print("Error: Could not import log_activity from work_log_tools.py.", file=sys.stderr)
    print("Ensure this script is in the same directory as work_log_tools.py.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Log an activity to the Work Log essence.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "description",
        type=str,
        help="The description of the activity to log."
    )
    parser.add_argument(
        "--category",
        type=str,
        default="general",
        help="The category of the activity (e.g., 'code_fix', 'investigation')."
    )
    args = parser.parse_args()

    try:
        entry = log_activity(args.description, category=args.category)
        print(f"Successfully logged activity to Work Log:")
        print(f"  Timestamp: {entry['timestamp']}")
        print(f"  Category:  {entry['category']}")
        print(f"  Description: {entry['description']}")
    except Exception as e:
        print(f"Error: Failed to log activity: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
