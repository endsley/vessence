import time
import sys
import os
from pathlib import Path

# Add project root to sys.path
VESSENCE_HOME = Path("/home/chieh/ambient/vessence")
sys.path.insert(0, str(VESSENCE_HOME))

from agent_skills.code_lock import code_edit_lock

print("Attempting to acquire code edit lock for 10 minutes...")
try:
    with code_edit_lock("jane-gemini", timeout=30):
        print("Lock acquired. Holding for 600 seconds (10 minutes)...")
        time.sleep(600)
    print("Lock released naturally.")
except TimeoutError as e:
    print(f"FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
