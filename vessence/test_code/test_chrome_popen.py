import subprocess
import time
import sys

def get_chrome_pids():
    try:
        output = subprocess.check_output(['pgrep', '-f', 'chrome']).decode().split()
        return set(output)
    except subprocess.CalledProcessError:
        return set()

def test_launch_chrome(url="about:blank"):
    pids_before = get_chrome_pids()
    print(f"PIDs before: {len(pids_before)}")

    print(f"Launching Chrome with Popen: {url}")
    # Simulate the logic in LocalComputer.py
    process = subprocess.Popen([
        "google-chrome",
        "--new-window",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
        url
    ])
    
    time.sleep(5)
    
    pids_after = get_chrome_pids()
    print(f"PIDs after: {len(pids_after)}")
    
    new_pids = pids_after - pids_before
    if new_pids:
        print(f"New PIDs found: {new_pids}")
        return True
    else:
        print("No new PIDs found.")
        return False

if __name__ == "__main__":
    success = test_launch_chrome()
    sys.exit(0 if success else 1)
