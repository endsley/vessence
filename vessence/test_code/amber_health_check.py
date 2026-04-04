#!/home/chieh/google-adk-env/adk-venv/bin/python
import subprocess
import os
import requests
import json
import ollama
from dotenv import load_dotenv
from google.genai import Client

# Load environment
VAULT_ROOT = "/home/chieh/vessence"
load_dotenv(os.path.join(VAULT_ROOT, ".env"))

def check_ps(pattern):
    try:
        result = subprocess.check_output(f"ps aux | grep -v grep | grep '{pattern}'", shell=True)
        return True, result.decode().strip().split('\n')[0]
    except:
        return False, "Not running"

def print_step(name, success, info=""):
    color = "\033[32m[PASS]\033[0m" if success else "\033[31m[FAIL]\033[0m"
    print(f"{color} {name:40} {info}")

def main():
    print("\n--- AMBER SYSTEM HEALTH CHECK ---\n")

    # 1. Process Checks
    brain_ok, brain_info = check_ps("adk web")
    print_step("Amber Brain (ADK Web Server)", brain_ok, brain_info[:50])

    bridge_ok, bridge_info = check_ps("discord_bridge.py")
    print_step("Discord Bridge", bridge_ok, bridge_info[:50])

    # 2. ADK Server Connectivity & Registration
    apps = []
    try:
        resp = requests.get("http://localhost:8000/list-apps", timeout=5)
        apps = resp.json()
        adk_ok = "agent" in apps or "amber" in apps
        print_step("ADK App Registration", adk_ok, f"Apps found: {apps}")
    except Exception as e:
        print_step("ADK Connectivity", False, str(e))

    # 3. End-to-End Brain Test (Simulate Message)
    if apps:
        app_name = "amber"
        url = "http://localhost:8000/run"
        payload = {
            "app_name": app_name,
            "user_id": "health_check_user",
            "session_id": "health_check_session",
            "new_message": {"parts": [{"text": "hi"}], "role": "user"}
        }
        try:
            # Create session: /apps/{app_name}/users/{user_id}/sessions/{session_id}
            requests.post(f"http://localhost:8000/apps/{app_name}/users/health_check_user/sessions/health_check_session", json={})
            
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                events = data if isinstance(data, list) else data.get("events", [])
                has_text = any("text" in p for e in events if e.get("content") for p in e["content"].get("parts", []))
                print_step("End-to-End Brain Response", has_text, f"Received {len(events)} events")
            else:
                print_step("End-to-End Brain Response", False, f"Status {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print_step("End-to-End Brain Response", False, str(e))

    # 4. Model Checks
    # Gemini
    try:
        genai_client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
        genai_client.models.generate_content(model="gemini-3-flash-preview", contents="ping")
        print_step("Gemini API (3-flash-preview)", True, "Responsive")
    except Exception as e:
        print_step("Gemini API", False, str(e))

    # Ollama
    try:
        models = ollama.list()
        qwen_found = any(m.model.startswith("qwen2.5-coder:14b") for m in models.models)
        print_step("Local Ollama (Qwen)", qwen_found, "qwen2.5-coder:14b found")
    except Exception as e:
        print_step("Local Ollama", False, str(e))

    # 5. Config Checks
    token = os.getenv("DISCORD_TOKEN")
    channel = os.getenv("DISCORD_CHANNEL_ID")
    print_step("Discord Token Found", bool(token), f"{token[:10]}..." if token else "MISSING")
    print_step("Discord Channel ID Found", bool(channel), channel or "MISSING")

    # 6. Bridge File Checks
    bridge_path = "/home/chieh/vessence/discord_bridge.py"
    if os.path.exists(bridge_path):
        with open(bridge_path, 'r') as f:
            content = f.read()
            has_re = "import re" in content
            print_step("Bridge Import Check (re)", has_re, "import re found" if has_re else "MISSING")

    print("\n--- CHECK COMPLETE ---\n")

if __name__ == "__main__":
    main()
