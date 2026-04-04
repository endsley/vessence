
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / 'agent_skills'))
from qwen_orchestrator import QwenOrchestrator
from jane.config import LOGS_DIR, VESSENCE_HOME

def main():
    with open(os.path.join(VESSENCE_HOME, 'jane', 'jane_session_wrapper.py'), 'r') as f:
        code = f.read()
    
    # Extract some log context
    def get_tail(path, n=50):
        try:
            with open(path, 'r') as f:
                return "".join(f.readlines()[-n:])
        except:
            return f"Error reading {path}"

    bridge_log = get_tail(os.environ.get('JANE_BRIDGE_LOG', str(Path.home() / 'gemini_cli_bridge' / 'bridge.log')))
    server_log = get_tail(os.path.join(LOGS_DIR, 'server.log'))
    crash_log = get_tail(os.path.join(LOGS_DIR, 'crash.log'))

    task_desc = f"""
Analyze the following script for logical flaws, race conditions, or deadlocks.
Focus on previous "fixes" mentioned: ANSI stripping, idle-timeout turn detection, and background memory sync.
Determine if they are functioning correctly or causing issues.

SOURCE CODE (jane_session_wrapper.py):
{code}

LOG CONTEXT (bridge.log):
{bridge_log}

LOG CONTEXT (server.log):
{server_log}

LOG CONTEXT (crash.log):
{crash_log}
"""

    orchestrator = QwenOrchestrator()
    if not orchestrator.check_hardware_lock():
        print("Hardware lock failed.")
        return

    print("Running Stage 6: Audit...")
    audit_report = orchestrator.stage_6_audit(task_desc)
    print("\n--- AUDIT REPORT ---")
    print(audit_report)

    # Save audit report for reference
    with open(os.path.join(VESSENCE_HOME, 'audit_report.md'), 'w') as f:
        f.write(audit_report)

if __name__ == "__main__":
    main()
