"""
onboarding/main.py — Vessence first-run setup wizard.
Runs on port 3000. Detects first run, guides user through setup,
writes .env, runs identity interview, then redirects to vault.localhost.
"""
import os
import json
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DATA_DIR   = Path(os.environ.get("VESSENCE_DATA_HOME", os.environ.get("AMBIENT_HOME", "/data")))
VAULT_DIR  = Path(os.environ.get("VAULT_HOME", "/vault"))
ENV_FILE   = DATA_DIR / ".env"
PROFILE    = DATA_DIR / "user_profile.md"

app = FastAPI(title="Vessence Setup")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def default_auth_method_for_brain(brain: str) -> str:
    return "account" if brain == "claude" else "apikey"


def _read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw_line in ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── First-run detection ───────────────────────────────────────────────────────

def onboarding_complete() -> bool:
    """Onboarding is complete only after config exists and the identity interview has been saved."""
    if not ENV_FILE.exists() or not PROFILE.exists():
        return False
    values = _read_env_values()
    user_name = values.get("USER_NAME", "").strip()
    return bool(user_name)


def is_first_run() -> bool:
    """Treat setup as incomplete until both .env and user_profile.md exist."""
    return not onboarding_complete()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_first_run():
        env_values = _read_env_values()
        domain = env_values.get("CLOUDFLARE_DOMAIN", "").strip()
        vault_url = f"https://vault.{domain}" if domain else "http://localhost:8081/vault"
        jane_url  = f"https://jane.{domain}"  if domain else "http://localhost:8081"
        current_brain = env_values.get("JANE_BRAIN", "gemini")
        return templates.TemplateResponse(request, "settings.html", context={
            "vault_url": vault_url,
            "jane_url": jane_url,
            "current_brain": current_brain,
            "current_cloudflare_domain": domain,
            "current_allowed_google_emails": env_values.get("ALLOWED_GOOGLE_EMAILS", ""),
            "web_permissions_enabled": env_values.get("JANE_WEB_PERMISSIONS", "0") == "1",
            "google_oauth_configured": bool(
                env_values.get("GOOGLE_CLIENT_ID", "").strip()
                and env_values.get("GOOGLE_CLIENT_SECRET", "").strip()
                and env_values.get("ALLOWED_GOOGLE_EMAILS", "").strip()
            ),
        })
    env_values = _read_env_values()
    preset_brain = env_values.get("JANE_BRAIN", "").strip().lower()
    if preset_brain not in ("gemini", "claude", "openai"):
        preset_brain = ""
    return templates.TemplateResponse(request, "setup.html", context={
        "step": "welcome",
        "preset_brain": preset_brain,
        "preset_auth_method": default_auth_method_for_brain(preset_brain) if preset_brain else "account",
        "initial_user_name": env_values.get("USER_NAME", "").strip(),
        "jane_url": "http://localhost:8081",
    })


# ── Submit setup form ─────────────────────────────────────────────────────────

@app.post("/api/setup")
async def setup(request: Request):
    body = await request.json()

    user_name  = body.get("user_name", "").strip()
    jane_brain = body.get("jane_brain", "claude")
    google_api_key = body.get("google_api_key", "").strip()
    anthropic_api_key = body.get("anthropic_api_key", "").strip()
    openai_api_key = body.get("openai_api_key", "").strip()
    create_minimal_profile = bool(body.get("create_minimal_profile"))
    api_key = (
        body.get("api_key", "").strip()
        or {
            "gemini": google_api_key,
            "claude": anthropic_api_key,
            "openai": openai_api_key,
        }.get(jane_brain, "")
    )
    google_client_id = body.get("google_client_id", "").strip()
    google_client_secret = body.get("google_client_secret", "").strip()
    allowed_google_emails = body.get("allowed_google_emails", "").strip()

    if not user_name and create_minimal_profile:
        user_name = "User"

    if not user_name:
        raise HTTPException(400, "Your name is required")

    if jane_brain not in ("claude", "openai", "gemini"):
        raise HTTPException(400, "Invalid provider. Choose claude, openai, or gemini.")

    google_oauth_values = [
        google_client_id,
        google_client_secret,
        allowed_google_emails,
    ]
    if any(google_oauth_values) and not all(google_oauth_values):
        raise HTTPException(400, "Google Sign-In setup is incomplete. Provide client ID, client secret, and allowed emails together.")

    session_secret = secrets.token_hex(32)

    # Map provider to the correct API key env var name
    api_key_var = {
        "claude": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }.get(jane_brain, "GOOGLE_API_KEY")

    # Gemini CLI checks GEMINI_API_KEY first, then GOOGLE_API_KEY — set both
    if api_key and jane_brain == "gemini":
        api_key_line = f"\nGOOGLE_API_KEY={api_key}\nGEMINI_API_KEY={api_key}\n"
    elif api_key:
        api_key_line = f"\n{api_key_var}={api_key}\n"
    else:
        api_key_line = "\n"

    # Claude supports web-based tool permission gating via PreToolUse hooks;
    # other providers run fully autonomous (no hook support).
    web_permissions = "1" if jane_brain == "claude" else "0"

    google_oauth_lines = ""
    if all(google_oauth_values):
        google_oauth_lines = (
            f"GOOGLE_CLIENT_ID={google_client_id}\n"
            f"GOOGLE_CLIENT_SECRET={google_client_secret}\n"
            f"ALLOWED_GOOGLE_EMAILS={allowed_google_emails}\n"
        )

    env_content = f"""# Vessence environment — written by onboarding on first run
# Do not commit this file.

JANE_BRAIN={jane_brain}
USER_NAME={user_name}
{api_key_line}
{google_oauth_lines}\
SESSION_SECRET_KEY={session_secret}
JANE_WEB_PERMISSIONS={web_permissions}

VESSENCE_DATA_HOME=/data
VAULT_HOME=/vault
CHROMA_HOST=chromadb
CHROMA_PORT=8000
"""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text(env_content)

    if create_minimal_profile and not PROFILE.exists():
        PROFILE.write_text(_build_profile({
            "name": user_name,
            "tone": "casual",
            "extra": "User completed quick onboarding setup. Profile can be edited later from Vessence.",
        }))

    return JSONResponse({"success": True, "next": "/success" if create_minimal_profile else "/interview"})


# ── CLI Login (OAuth flow — proxied to Jane container where CLI is installed) ──

JANE_URL = os.environ.get("JANE_URL", "http://jane:8090")


@app.post("/api/cli-login")
async def cli_login(request: Request):
    """Proxy CLI login request to the Jane container."""
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{JANE_URL}/api/cli-login", json=body)
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "Jane container is not ready yet. Please wait a moment and try again."})
    except Exception as e:
        return JSONResponse({"error": f"Could not reach Jane: {e}"})


@app.get("/api/cli-login/status")
async def cli_login_status():
    """Proxy CLI login status check to the Jane container."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{JANE_URL}/api/cli-login/status")
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({"authenticated": False})


@app.post("/api/cli-login/code")
async def cli_login_code(request: Request):
    """Proxy auth-code submission to the Jane container."""
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{JANE_URL}/api/cli-login/code", json=body)
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"ok": False, "error": "Jane container is not ready yet. Please wait a moment and try again."}, status_code=503)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Could not reach Jane: {e}"}, status_code=500)


# ── Identity interview ────────────────────────────────────────────────────────

@app.get("/interview", response_class=HTMLResponse)
async def interview_page(request: Request):
    return templates.TemplateResponse(request, "interview.html")


@app.post("/api/interview/submit")
async def interview_submit(request: Request):
    """Receive interview answers, generate user_profile.md, write to host."""
    answers = await request.json()
    profile_md = _build_profile(answers)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(profile_md)
    return JSONResponse({"success": True, "next": "/success"})


def _build_profile(a: dict) -> str:
    name        = a.get("name", "")
    pronouns    = a.get("pronouns", "")
    role        = a.get("role", "")
    location    = a.get("location", "")
    topics      = a.get("topics", "")
    tone        = a.get("tone", "")
    family      = a.get("family", "")
    goals       = a.get("goals", "")
    personality = a.get("personality", "")
    extra       = a.get("extra", "")

    return f"""# User Profile
# Generated by Vessence onboarding. Edit freely — Amber and Jane read this at startup.

## Identity
name: {name}
pronouns: {pronouns or "not specified"}
location: {location or "not specified"}

## Professional
role: {role or "not specified"}
current_focus: {goals or "not specified"}

## Interests & Topics
{topics or "not specified"}

## Relationships & Family
{family or "not specified"}

## Communication Preferences
tone: {tone or "direct and friendly"}
address_me_as: {name.split()[0] if name else "not specified"}

## Personality Notes
{personality or "not specified"}

## Extra Context
{extra or "nothing added yet"}

---
# How agents use this file:
# - Amber reads it to personalize how she addresses you and what she remembers
# - Jane reads it to understand your background and calibrate her responses
# - Both agents read it at the start of every session
# - Edit this file directly to update anything — changes take effect on next restart
"""


# ── Settings (post-setup) ──────────────────────────────────────────────────────

@app.post("/api/settings")
async def save_settings(request: Request):
    """Patch specific keys in the existing .env without overwriting everything."""
    body = await request.json()

    if not ENV_FILE.exists():
        return JSONResponse({"success": False, "error": ".env not found — run setup first."})

    env_lines = ENV_FILE.read_text().splitlines()
    jane_brain = body.get("jane_brain", "").strip()
    updates = {
        "JANE_BRAIN":               jane_brain,
        "GOOGLE_API_KEY":           body.get("google_api_key", "").strip(),
        "GOOGLE_CLIENT_ID":         body.get("google_client_id", "").strip(),
        "GOOGLE_CLIENT_SECRET":     body.get("google_client_secret", "").strip(),
        "ALLOWED_GOOGLE_EMAILS":    body.get("allowed_google_emails", "").strip(),
        "ANTHROPIC_API_KEY":        body.get("anthropic_api_key", "").strip(),
        "OPENAI_API_KEY":           body.get("openai_api_key", "").strip(),
        "CLOUDFLARE_TUNNEL_TOKEN":  body.get("cloudflare_tunnel_token", "").strip(),
        "CLOUDFLARE_DOMAIN":        body.get("cloudflare_domain", "").strip(),
        "DISCORD_TOKEN":            body.get("discord_token", "").strip(),
        "DISCORD_CHANNEL_ID":       body.get("discord_channel_id", "").strip(),
        "JANE_WEB_PERMISSIONS":     body.get("jane_web_permissions", "").strip(),
    }
    # Remove empty updates (don't blank keys the user left empty in the form)
    updates = {k: v for k, v in updates.items() if v}

    # Update existing lines, collect keys that were found
    found_keys: set[str] = set()
    new_lines = []
    for line in env_lines:
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            found_keys.add(key)
        else:
            new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, val in updates.items():
        if key not in found_keys:
            new_lines.append(f"{key}={val}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n")
    return JSONResponse({"success": True})


# ── API key validation (used by settings page) ───────────────────────────────

@app.post("/api/validate-key")
async def validate_key(request: Request):
    body = await request.json()
    key_type = body.get("type")
    key_value = body.get("value", "").strip()

    if key_type == "google":
        if not key_value.startswith("AIzaSy") or len(key_value) < 35:
            return JSONResponse({"valid": False, "error": "Doesn't look like a Google API key (should start with AIzaSy, 39 chars)."})
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": key_value}
                )
            if resp.status_code == 200:
                return JSONResponse({"valid": True})
            elif resp.status_code == 400:
                return JSONResponse({"valid": False, "error": "Invalid API key."})
            else:
                return JSONResponse({"valid": False, "error": f"Unexpected response ({resp.status_code})."})
        except Exception as e:
            return JSONResponse({"valid": False, "error": f"Network error: {str(e)[:100]}"})

    elif key_type == "anthropic":
        if not key_value.startswith("sk-ant-"):
            return JSONResponse({"valid": False, "error": "Doesn't look like an Anthropic key (should start with sk-ant-)."})
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": key_value, "anthropic-version": "2023-06-01"}
                )
            valid = resp.status_code == 200
            return JSONResponse({"valid": valid, "error": None if valid else "Key rejected."})
        except Exception as e:
            return JSONResponse({"valid": False, "error": f"Network error: {str(e)[:100]}"})

    elif key_type == "openai":
        if not key_value.startswith("sk-"):
            return JSONResponse({"valid": False, "error": "Doesn't look like an OpenAI key (should start with sk-)."})
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key_value}"}
                )
            valid = resp.status_code == 200
            return JSONResponse({"valid": valid, "error": None if valid else "Key rejected."})
        except Exception as e:
            return JSONResponse({"valid": False, "error": f"Network error: {str(e)[:100]}"})

    return JSONResponse({"valid": False, "error": "Unknown key type"})


# ── Success screen ────────────────────────────────────────────────────────────

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    if not onboarding_complete():
        return RedirectResponse(url="/", status_code=303)
    domain = os.environ.get("CLOUDFLARE_DOMAIN", "")
    if domain:
        vault_url = f"https://vault.{domain}"
        jane_url  = f"https://jane.{domain}"
    else:
        vault_url = "http://localhost:8081/vault"
        jane_url  = "http://localhost:8081"
    return templates.TemplateResponse(request, "success.html", context={
        "vault_url": vault_url,
        "jane_url": jane_url,
    })
