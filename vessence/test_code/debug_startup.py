
import subprocess
import time
import os

VENV_BIN = "/home/chieh/google-adk-env/adk-venv/bin"

def start_process(cmd, cwd, log_file):
    with open(log_file, "w") as f:
        return subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=f, start_new_session=True)

print("Starting Amber Brain...")
brain = start_process([f"{VENV_BIN}/adk", "web", "--memory_service_uri", "localvector:///home/chieh/ambient/vector_db", "--port", "8000", "/home/chieh/vessence"], "/home/chieh/vessence", "/home/chieh/vessence/server.log")

time.sleep(5)

print("Starting Amber Bridge...")
amber_bridge = start_process([f"{VENV_BIN}/python", "discord_bridge.py"], "/home/chieh/vessence", "/home/chieh/vessence/bridge.log")

print("Starting Jane Bridge...")
jane_bridge = start_process([f"{VENV_BIN}/python", "bridge.py"], "/home/chieh/gemini_cli_bridge", "/home/chieh/gemini_cli_bridge/bridge.log")

time.sleep(10)

print(f"Brain PID: {brain.pid}, returncode: {brain.poll()}")
print(f"Amber Bridge PID: {amber_bridge.pid}, returncode: {amber_bridge.poll()}")
print(f"Jane Bridge PID: {jane_bridge.pid}, returncode: {jane_bridge.poll()}")
