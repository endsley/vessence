import webbrowser
import sys
import time
import subprocess

def get_chrome_pids():
    try:
        output = subprocess.check_output(['pgrep', '-f', 'chrome']).decode().split()
        return set(output)
    except subprocess.CalledProcessError:
        return set()

pids_before = get_chrome_pids()
print(f"PIDs before: {len(pids_before)}")

success = webbrowser.open('about:blank')
print(f"webbrowser.open returned: {success}")

time.sleep(5) # Wait for browser to start

pids_after = get_chrome_pids()
print(f"PIDs after: {len(pids_after)}")

new_pids = pids_after - pids_before
if new_pids:
    print(f"New PIDs found: {new_pids}")
else:
    print("No new PIDs found.")

sys.exit(0 if success and new_pids else 1)
