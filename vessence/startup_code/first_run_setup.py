#!/usr/bin/env python3
"""first_run_setup.py — Configure Vessence's .env file.

Single source of truth for all .env onboarding logic. Called either:
  - directly by the user once the venv + deps + data dirs exist, or
  - by setup.sh as the "configure Jane" phase.

Handles: copying .env.example, generating the session secret, detecting the AI
CLI, prompting for the user's name, API keys, remote-access / OAuth setup, and
an optional weather location. Existing .env values and comments are preserved
on re-run.

Usage:
    python vessence/startup_code/first_run_setup.py
"""

import os
import re
import secrets
import shutil
import sys
from pathlib import Path

VESSENCE_HOME = Path(__file__).resolve().parents[1]
VESSENCE_DATA_HOME = Path(
    os.environ.get("VESSENCE_DATA_HOME", str(VESSENCE_HOME.parent / "vessence-data"))
)
ENV_FILE = VESSENCE_DATA_HOME / ".env"
ENV_EXAMPLE = VESSENCE_HOME / ".env.example"


# ─────────────────────────────────────────────────────────────────────────────
# .env I/O — preserves comments and ordering on update
# ─────────────────────────────────────────────────────────────────────────────


def read_env() -> dict[str, str]:
    """Parse .env into a dict (comments and blank lines dropped)."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        env[key.strip()] = val.strip()
    return env


def update_env(updates: dict[str, str]) -> None:
    """Update keys in .env in place, preserving existing comments and order.

    Keys not already present are appended at the end. No-ops for empty values.
    """
    updates = {k: v for k, v in updates.items() if v != ""}
    if not updates:
        return

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []

    written: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                written.add(key)
                continue
        out.append(line)

    missing = {k: v for k, v in updates.items() if k not in written}
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# Added by first_run_setup.py")
        for k, v in missing.items():
            out.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(out) + "\n")


def bootstrap_env_file() -> None:
    """Ensure .env exists (copy from .env.example) and has a real session secret."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.exists():
        if not ENV_EXAMPLE.exists():
            print(f"  ✗ {ENV_EXAMPLE} not found — cannot create config.")
            sys.exit(1)
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print(f"  → Copied {ENV_EXAMPLE.name} → {ENV_FILE}")

    text = ENV_FILE.read_text()
    if "SESSION_SECRET_KEY=changeme-generate-a-real-secret" in text or re.search(
        r"^SESSION_SECRET_KEY=\s*$", text, flags=re.M
    ):
        new_secret = secrets.token_hex(32)
        text = re.sub(
            r"^SESSION_SECRET_KEY=.*", f"SESSION_SECRET_KEY={new_secret}", text, flags=re.M
        )
        ENV_FILE.write_text(text)
        print("  → Generated SESSION_SECRET_KEY")


# ─────────────────────────────────────────────────────────────────────────────
# Detection + prompting helpers
# ─────────────────────────────────────────────────────────────────────────────


def detect_cli_provider() -> tuple[str | None, str | None]:
    """Return (provider, path) for the first AI CLI found in PATH."""
    for name, provider in (("claude", "claude"), ("gemini", "gemini"), ("codex", "openai")):
        path = shutil.which(name)
        if path:
            return provider, path
    return None, None


def ask(prompt: str, default: str = "", required: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else (" (required)" if required else " (optional)")
        val = input(f"{prompt}{suffix}: ").strip()
        if val:
            return val
        if default:
            return default
        if not required:
            return ""
        print("  This value is required.")


def open_browser(url: str) -> None:
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Provider API key prompts
# ─────────────────────────────────────────────────────────────────────────────


def prompt_api_keys(provider: str, existing_env: dict[str, str], new_env: dict[str, str]) -> None:
    """Prompt for the API keys the chosen brain needs."""
    if provider == "claude":
        print("  Claude Code authenticates via its own login — no API key needed for the brain.")
        print("  A Google API key is optional but useful for weather + background services.")
        if existing_env.get("GOOGLE_API_KEY"):
            print("  ✓ GOOGLE_API_KEY already set")
            return
        print("  Get a free one at: https://aistudio.google.com → Get API key")
        key = ask("  Google API key (or press Enter to skip)")
        if key:
            new_env["GOOGLE_API_KEY"] = key
    elif provider == "gemini":
        if existing_env.get("GOOGLE_API_KEY"):
            print("  ✓ GOOGLE_API_KEY already set")
            return
        print("  Jane on Gemini needs a Google API key (free).")
        print("  Get one at: https://aistudio.google.com → Get API key  (looks like AIzaSy...)")
        key = ask("  Google API key")
        if key:
            new_env["GOOGLE_API_KEY"] = key
        else:
            print("  ⚠ Jane won't work without this. Add it to .env later.")
    elif provider == "openai":
        if existing_env.get("OPENAI_API_KEY"):
            print("  ✓ OPENAI_API_KEY already set")
            return
        print("  Jane on Codex needs an OpenAI API key.")
        print("  Get one at: https://platform.openai.com/api-keys  (looks like sk-proj-...)")
        key = ask("  OpenAI API key")
        if key:
            new_env["OPENAI_API_KEY"] = key
        else:
            print("  ⚠ Jane won't work without this. Add it to .env later.")


# ─────────────────────────────────────────────────────────────────────────────
# Google OAuth walkthrough (for remote access)
# ─────────────────────────────────────────────────────────────────────────────


def guide_google_oauth_setup(env: dict) -> None:
    """Walk the user through Google OAuth setup step-by-step."""
    print()
    print("─" * 60)
    print("  GOOGLE SIGN-IN SETUP — Why we need this")
    print("─" * 60)
    print()
    print("  When you access Jane from your phone or another device, the server")
    print("  needs to know it's really YOU and not a stranger who guessed your URL.")
    print()
    print("  Google sign-in is the easiest way: you click 'Sign in with Google',")
    print("  Google verifies your identity, and tells the server 'yes, this is")
    print("  the right person.' No passwords to remember, no extra accounts.")
    print()
    print("  This requires creating a free Google Cloud project (5 minutes).")
    print("  I'll walk you through every step.")
    print()
    input("  Press Enter to continue... ")
    print()

    print("─" * 60)
    print("  STEP 1: Create a Google Cloud project")
    print("─" * 60)
    print()
    print("  Opening: https://console.cloud.google.com/projectcreate")
    print()
    print("  In the page that opens:")
    print("    1. Project name: 'Vessence' (or anything you like)")
    print("    2. Click CREATE")
    print("    3. Wait ~10 seconds for the project to be created")
    print("    4. Make sure the new project is selected at the top of the page")
    print()
    open_browser("https://console.cloud.google.com/projectcreate")
    input("  Press Enter when done... ")
    print()

    print("─" * 60)
    print("  STEP 2: Configure the OAuth consent screen")
    print("─" * 60)
    print()
    print("  This is what users see when they sign in — name of your app, etc.")
    print()
    print("  Opening: https://console.cloud.google.com/apis/credentials/consent")
    print()
    print("  In the page that opens:")
    print("    1. User Type: External → CREATE")
    print("    2. App name: 'Vessence Jane' (or anything)")
    print("    3. User support email: your email")
    print("    4. Developer contact: your email")
    print("    5. Click SAVE AND CONTINUE through Scopes (skip — leave defaults)")
    print("    6. Test users: ADD USERS → enter your email → SAVE AND CONTINUE")
    print("    7. Click BACK TO DASHBOARD")
    print()
    open_browser("https://console.cloud.google.com/apis/credentials/consent")
    input("  Press Enter when done... ")
    print()

    print("─" * 60)
    print("  STEP 3: Create OAuth credentials")
    print("─" * 60)
    print()
    print("  Now we'll create the actual Client ID and Secret.")
    print()
    print("  Opening: https://console.cloud.google.com/apis/credentials")
    print()
    print("  In the page that opens:")
    print("    1. Click + CREATE CREDENTIALS at the top → OAuth client ID")
    print("    2. Application type: Web application")
    print("    3. Name: 'Vessence Web' (or anything)")
    print()
    print("    4. Authorized redirect URIs — click ADD URI and add:")
    print("       http://localhost:8081/auth/google/callback")
    print("       (also add your remote URL if you have one, e.g.:")
    print("        https://YOUR_DOMAIN.vessences.com/auth/google/callback)")
    print()
    print("    5. Click CREATE")
    print("    6. A popup shows your Client ID and Client Secret — KEEP IT OPEN")
    print()
    open_browser("https://console.cloud.google.com/apis/credentials")
    input("  Press Enter when the popup is showing... ")
    print()

    print("─" * 60)
    print("  STEP 4: Paste your credentials below")
    print("─" * 60)
    print()
    while True:
        client_id = ask("  Client ID (ends with .apps.googleusercontent.com)", required=True)
        if ".apps.googleusercontent.com" in client_id:
            break
        print("  ⚠ That doesn't look right. Client ID ends with .apps.googleusercontent.com")
    client_secret = ask("  Client Secret (starts with GOCSPX-)", required=True)
    print()
    email = ask("  Your Google email (the one allowed to sign in)", required=True)
    print()

    env["GOOGLE_CLIENT_ID"] = client_id
    env["GOOGLE_CLIENT_SECRET"] = client_secret
    env["ALLOWED_GOOGLE_EMAILS"] = email

    print("─" * 60)
    print("  ✓ Google sign-in configured!")
    print("─" * 60)
    print()
    print("  After the server starts, sign in at:")
    print("    http://localhost:8081/auth/google")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 60)
    print("Vessence First-Run Setup")
    print("=" * 60)
    print()

    # Step 0 — .env bootstrap
    print("Step 0: Bootstrapping .env...")
    bootstrap_env_file()
    existing_env = read_env()
    new_env: dict[str, str] = {}
    print()

    # Step 1 — detect AI CLI
    print("Step 1: Detecting AI CLI provider...")
    provider, cli_path = detect_cli_provider()
    if provider:
        print(f"  ✓ Found {provider} CLI at {cli_path}")
        new_env["JANE_BRAIN"] = provider
        bin_key = {"claude": "CLAUDE_BIN", "gemini": "GEMINI_BIN", "openai": "CODEX_BIN"}[provider]
        new_env[bin_key] = cli_path
    else:
        print("  ✗ No AI CLI found in PATH. Vessence needs one of:")
        print("    - claude (Claude Code) — https://docs.claude.com/claude-code")
        print("    - gemini (Gemini CLI)  — https://github.com/google-gemini/gemini-cli")
        print("    - codex  (Codex CLI)   — https://github.com/openai/codex")
        manual = ask("  Install one, then either paste the path now or re-run this script")
        if not manual:
            print("  Aborting setup.")
            return 1
        new_env["JANE_BRAIN"] = "claude"
        new_env["CLAUDE_BIN"] = manual
        provider = "claude"
    print()

    # Step 2 — provider API keys
    print("Step 2: API keys")
    prompt_api_keys(provider, existing_env, new_env)
    print()

    # Step 3 — user identity
    print("Step 3: Your identity")
    existing_name = existing_env.get("USER_NAME")
    if existing_name:
        print(f"  ✓ USER_NAME already set: {existing_name}")
        new_env["USER_NAME"] = existing_name
    else:
        new_env["USER_NAME"] = ask("  Your name", default="User")
    print()

    # Step 4 — access mode
    print("Step 4: How do you want to access Jane?")
    print()
    print("  [1] Local only — chat with Jane on this computer at http://localhost:8081")
    print("      (no setup needed, no auth required for localhost)")
    print()
    print("  [2] Remote access — use Jane from your phone, tablet, or other devices")
    print("      Requires a Google Cloud OAuth client for sign-in (5-min setup).")
    print()
    access_mode = ask("  Choose [1] or [2]", default="1")
    if access_mode == "2":
        guide_google_oauth_setup(new_env)
    print()

    # Step 5 — weather location (optional)
    print("Step 5: Weather location (optional)")
    if existing_env.get("WEATHER_LOCATION"):
        print(f"  ✓ Already set: {existing_env.get('WEATHER_LOCATION')}")
    else:
        loc = ask("  City, State (e.g., 'Boston, MA') — or skip")
        if loc:
            new_env["WEATHER_LOCATION"] = loc
    print()

    # Step 6 — write .env
    print("Step 6: Writing configuration...")
    update_env(new_env)
    print(f"  → Updated {ENV_FILE}")
    print()

    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Start the server: systemctl --user start jane-web.service")
    print("     (on macOS: launchctl load ~/Library/LaunchAgents/com.vessence.jane-web.plist)")
    print("  2. Open Jane: http://localhost:8081/")
    if access_mode == "2":
        print("  3. Sign in with Google at http://localhost:8081/auth/google")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
