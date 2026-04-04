"""amber_proxy.py — Proxy chat messages to Amber ADK API."""
import sys
import os
import json
import secrets
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from jane.config import (
    ADK_SERVER_URL,
    ENV_FILE_PATH,
    HTTP_TIMEOUT_ADK_RUN,
    LOGS_DIR,
    VAULT_DIR,
    VAULT_TUNNEL_LOG,
)

load_dotenv(ENV_FILE_PATH)

BRAIN_MODE = os.getenv("AMBER_BRAIN_MODEL", "gemini").lower()
LOCAL_BRAIN = BRAIN_MODE in ("gemma", "gemma3", "qwen", "qwen-local")


def _unwrap_local_text(raw: str) -> str:
    """Local models (gemma/qwen) sometimes emit the ADK result JSON as plain text.
    Unwrap it to get the human-readable string inside."""
    if not raw.strip().startswith("{"):
        return raw
    try:
        d = json.loads(raw)
        result = d.get("result", [])
        if isinstance(result, list):
            parts = [r.get("text", "") for r in result if isinstance(r, dict) and r.get("text")]
            if parts:
                return "\n".join(parts)
    except Exception:
        pass
    return raw

ADK_BASE = ADK_SERVER_URL  # http://localhost:8000
WEB_SESSION_PREFIX = "vault_web_"


async def ensure_session(user_id: str, session_id: str):
    """Create ADK session if it doesn't exist."""
    url = f"{ADK_BASE}/apps/amber/users/{user_id}/sessions/{session_id}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json={}, timeout=10)
            return r.status_code in (200, 201, 409)  # 409 = already exists
        except Exception:
            return False


def _vault_rel(file_uri: str) -> str | None:
    """Convert an absolute vault path to a vault-relative path for /api/files/serve/."""
    if file_uri and file_uri.startswith(VAULT_DIR):
        return file_uri[len(VAULT_DIR):].lstrip("/")
    return None


async def send_message(user_id: str, session_id: str, message: str, file_context: str = None) -> dict:
    """Send a message to Amber and return her response as {text, images}."""
    full_message = message
    if file_context:
        full_message = f"[Viewing file: {file_context}]\n\n{message}"
    # Prepend web context so the Vault UI stays in Amber's voice and avoids unnecessary tools.
    full_message = (
        "[WEB CHAT — you are Amber, not Jane. Respond in text only. "
        "Be warm, grounded, and personal. Do NOT use generate_speech unless explicitly asked.]\n\n"
        f"{full_message}"
    )

    await ensure_session(user_id, session_id)

    payload = {
        "app_name": "amber",
        "user_id": user_id,
        "session_id": session_id,
        "new_message": {
            "parts": [{"text": full_message}],
            "role": "user",
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{ADK_BASE}/run",
                json=payload,
                timeout=HTTP_TIMEOUT_ADK_RUN,
            )
            if r.status_code != 200:
                return {"text": f"⚠️ Amber is unavailable (HTTP {r.status_code})", "images": []}

            data = r.json()
            texts = []
            files = []  # list of {"src", "name", "mime", "is_image"}

            if isinstance(data, list):
                for event in data:
                    if not isinstance(event, dict):
                        continue
                    content = event.get("content", {})
                    if not isinstance(content, dict):
                        continue
                    for part in content.get("parts", []):
                        if not isinstance(part, dict):
                            continue
                        # Plain text (unwrap local-model JSON wrapper if needed)
                        if "text" in part and part["text"]:
                            txt = _unwrap_local_text(part["text"]) if LOCAL_BRAIN else part["text"]
                            if txt:
                                texts.append(txt)
                        # Local vault file — either top-level or in a functionResponse result
                        _file_parts = []
                        if "file_data" in part or "inline_data" in part:
                            _file_parts.append(part)
                        # ADK uses camelCase: functionResponse.response.result[]
                        if "functionResponse" in part:
                            result = part["functionResponse"].get("response", {}).get("result", [])
                            if isinstance(result, list):
                                _file_parts.extend(result)
                        for fp in _file_parts:
                            if not isinstance(fp, dict):
                                continue
                            if "file_data" in fp:
                                fd = fp["file_data"]
                                uri = fd.get("file_uri", "")
                                mime = fd.get("mime_type", "application/octet-stream")
                                rel = _vault_rel(uri)
                                if rel:
                                    files.append({
                                        "src": f"/api/files/serve/{rel}",
                                        "name": os.path.basename(uri),
                                        "mime": mime,
                                        "is_image": mime.startswith("image/"),
                                    })
                            if "inline_data" in fp:
                                idata = fp["inline_data"]
                                b64 = idata.get("data", "")
                                mime = idata.get("mime_type", "application/octet-stream")
                                name = idata.get("display_name", "file")
                                if b64:
                                    files.append({
                                        "src": f"data:{mime};base64,{b64}",
                                        "name": name,
                                        "mime": mime,
                                        "is_image": mime.startswith("image/"),
                                    })

            text = "\n".join(texts) if texts else ("_(no response)_" if not files else "")
            return {"text": text, "files": files}

        except httpx.TimeoutException:
            return {"text": "⚠️ Amber took too long to respond.", "files": []}
        except Exception as e:
            return {"text": f"⚠️ Error contacting Amber: {e}", "files": []}


def get_tunnel_url() -> str | None:
    """Read the current Cloudflare tunnel URL from cloudflared logs."""
    log_paths = [
        VAULT_TUNNEL_LOG,
        "/tmp/vault_tunnel.log",
    ]
    for log_path in log_paths:
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    for line in reversed(f.readlines()):
                        if "trycloudflare.com" in line:
                            # Extract URL
                            import re
                            match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                            if match:
                                return match.group(0)
            except Exception:
                pass
    return None
