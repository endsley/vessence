#!/usr/bin/env python3
"""main.py — Jane web UI (chat with Jane / Claude Code). Runs on port 8081.
Shares all templates and static assets with vault_web so UI changes propagate to both.
"""
import os
import sys
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, Cookie, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import asyncio
import aiofiles
import base64
import hashlib
import json
import logging
import re
import subprocess
import tempfile
import time
try:
    import chromadb
except ImportError:
    chromadb = None

CODE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_ROOT))
sys.path.insert(0, str(CODE_ROOT / "vault_web"))  # share vault_web modules

# ── Logging setup ─────────────────────────────────────────────────────────────
_DATA_HOME = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
_LOG_DIR = Path(_DATA_HOME) / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

from logging.handlers import RotatingFileHandler as _RotatingFileHandler
_file_handler = _RotatingFileHandler(
    _LOG_DIR / "jane_web.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_root_logger = logging.getLogger()
_root_logger.addHandler(_file_handler)
_root_logger.setLevel(logging.INFO)
# Ensure jane.proxy logger also writes here
logging.getLogger("jane.proxy").setLevel(logging.DEBUG)

_logger = logging.getLogger("jane.web")
_logger.info("=== Jane Web starting (PID %d) ===", os.getpid())

from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH, VAULT_DIR, TOOLS_DIR, ESSENCES_DIR, VESSENCE_DATA_HOME, ADD_FACT_SCRIPT, ADK_VENV_PYTHON, LOGS_DIR, PROMPT_LIST_PATH

load_dotenv(ENV_FILE_PATH)

from vault_web.database import init_db, get_db
from vault_web.auth import (
    create_session, validate_session,
    is_device_trusted, register_trusted_device,
    get_trusted_device_by_id, get_trusted_device_by_fingerprint,
    get_session_user, verify_otp,
    get_trusted_devices, revoke_device,
    device_fingerprint_from_request,
)
from vault_web.oauth import oauth, allowed_email, build_external_url, google_oauth_configured
from vault_web.files import (
    list_directory, get_file_metadata, update_description,
    generate_thumbnail, get_last_change_timestamp, safe_vault_path, is_text, TEXT_SIZE_LIMIT, get_mime,
    make_descriptive_filename, upsert_file_index_entry,
)
from vault_web.share import create_share, validate_share, list_shares, revoke_share
from vault_web.playlists import list_playlists, get_playlist, create_playlist, update_playlist, delete_playlist
try:
    from .jane_proxy import send_message, stream_message, get_tunnel_url, prewarm_session, end_session, run_prefetch_memory
except ImportError:
    from jane_proxy import send_message, stream_message, get_tunnel_url, prewarm_session, end_session, run_prefetch_memory

# ── Shared UI: point directly at vault_web's static + templates ──────────────
VAULT_WEB_DIR = CODE_ROOT / "vault_web"
BASE_DIR = Path(__file__).parent
MARKETING_DIR = CODE_ROOT / "marketing_site"
MARKETING_DOWNLOADS_DIR = MARKETING_DIR / "downloads"
import json as _json
try:
    _version_data = _json.loads((CODE_ROOT / "version.json").read_text())
    ANDROID_VERSION = _version_data["version_name"]
    _ANDROID_VERSION_CODE = _version_data["version_code"]
except FileNotFoundError:
    ANDROID_VERSION = "0.1.94"
    _ANDROID_VERSION_CODE = 207

# Startup validation: ensure the APK for the advertised version actually exists
_expected_apk = MARKETING_DOWNLOADS_DIR / f"vessences-android-v{ANDROID_VERSION}.apk"
if not _expected_apk.exists():
    import logging as _logging
    _logging.getLogger("jane.web").critical(
        "APK MISSING: version.json says v%s but %s does not exist! "
        "Run startup_code/bump_android_version.py to build it.",
        ANDROID_VERSION, _expected_apk,
    )
elif _expected_apk.stat().st_size < 1_000_000:  # < 1MB = likely corrupt
    import logging as _logging
    _logging.getLogger("jane.web").critical(
        "APK CORRUPT: %s is only %d bytes — likely not a valid APK. Rebuild with bump_android_version.py.",
        _expected_apk, _expected_apk.stat().st_size,
    )

def _find_latest(pattern: str) -> Optional[Path]:
    """Return the newest file matching a glob pattern in MARKETING_DOWNLOADS_DIR, or None."""
    matches = sorted(MARKETING_DOWNLOADS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None

PUBLIC_RELEASE_DOWNLOADS = {
    # Raw compose file for advanced users
    "docker-compose.yml": MARKETING_DIR / "docker-compose.yml",
    # Docker image tarball
    "vessence-docker-0.0.43.tar.gz": MARKETING_DOWNLOADS_DIR / "vessence-docker-0.0.43.tar.gz",
    # Universal Installer (bundled source + scripts)
    "vessence-installer-0.0.42.zip": MARKETING_DOWNLOADS_DIR / "vessence-installer-0.0.42.zip",
    # NOTE: Android APK entries are resolved DYNAMICALLY at request time via
    # _resolve_android_apk_path() — they are intentionally NOT in this static
    # dict, because the version bumps between jane-web restarts and we don't
    # want to force a restart on every APK deploy. See downloads handler.
    "vessences-android-package.zip": MARKETING_DOWNLOADS_DIR / "vessences-android-package.zip",
    # Legacy (keep for existing links)
    "vessence-installer-0.0.41.zip": MARKETING_DOWNLOADS_DIR / "vessence-installer-0.0.41.zip",
}


def _resolve_android_apk_path(filename: str) -> "Path | None":
    """Resolve an Android APK download filename to a real path at request time.

    Matches two shapes:
      - "vessences-android.apk"            → latest via version.json lookup
      - "vessences-android-v<X.Y.Z>.apk"   → specific version if the file exists

    Returns None if the filename doesn't match the APK pattern or the file is
    missing. Called from the /downloads/{filename} route handler.
    """
    if filename == "vessences-android.apk":
        # Unversioned alias — always points at the current version from version.json.
        try:
            vdata = _json.loads((CODE_ROOT / "version.json").read_text())
            current_version = vdata.get("version_name")
            if current_version:
                versioned = MARKETING_DOWNLOADS_DIR / f"vessences-android-v{current_version}.apk"
                if versioned.exists():
                    return versioned
        except Exception:
            pass
        # Fallback: the deploy script writes a second copy at this unversioned path.
        alias = MARKETING_DOWNLOADS_DIR / "vessences-android.apk"
        return alias if alias.exists() else None
    # Versioned pattern.
    if filename.startswith("vessences-android-v") and filename.endswith(".apk"):
        path = MARKETING_DOWNLOADS_DIR / filename
        return path if path.exists() else None
    return None

# Unversioned aliases that resolve to the latest versioned installer zip at request time
_INSTALLER_GLOBS = {
    "vessence-windows-installer.zip": "vessence-windows-installer-v*.zip",
    "vessence-mac-installer.zip": "vessence-mac-installer-v*.zip",
    "vessence-linux-installer.zip": "vessence-linux-installer-v*.zip",
}

app = FastAPI(title="Jane")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "changeme"))
app.mount("/static", StaticFiles(directory=VAULT_WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=VAULT_WEB_DIR / "templates")


# ── Request logging middleware ────────────────────────────────────────────────
def _touch_idle_state():
    """Update idle_state.json so the prompt queue runner knows user is active."""
    try:
        import json as _j
        from jane.config import IDLE_STATE_PATH
        Path(IDLE_STATE_PATH).write_text(_j.dumps({
            "last_active_ts": time.time(),
            "last_active_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }))
    except Exception:
        pass

@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        # Static assets: CSS, JS, images, fonts — cache at Cloudflare edge for 1 day
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.startswith("/api/briefing/image/"):
        # Briefing images: cache for 1 hour (refreshed daily)
        response.headers["Cache-Control"] = "public, max-age=3600"
    elif path.startswith("/api/"):
        # API responses: never cache (dynamic data)
        response.headers["Cache-Control"] = "no-store"
    else:
        # HTML pages: always revalidate (but allow conditional GET)
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    path = request.url.path
    method = request.method
    # Update idle state for non-polling requests (so queue runner knows user is active)
    is_poll = path in ("/api/jane/announcements", "/health", "/api/files/changes", "/api/jane/live")
    if not is_poll and method in ("POST", "GET") and "/api/" in path:
        _touch_idle_state()
    try:
        response = await call_next(request)
        if not is_poll:
            elapsed_ms = int((time.time() - start) * 1000)
            _logger.info("%s %s → %d (%dms)", method, path, response.status_code, elapsed_ms)
        return response
    except Exception as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        _logger.exception("Unhandled error in %s %s after %dms: %s", method, path, elapsed_ms, exc)
        raise

SESSION_COOKIE = "jane_session"
TRUSTED_DEVICE_COOKIE = "jane_trusted_device"
STATIC_DIR = VAULT_WEB_DIR / "static"
ANNOUNCEMENTS_PATH = Path(ENV_FILE_PATH).parent / "data" / "jane_announcements.jsonl"


def _session_log_id(session_id: Optional[str]) -> str:
    return session_id[:12] if session_id else "none"


def _client_ip(request: Request) -> str:
    return getattr(request.client, "host", "unknown") or "unknown"


def _login_context(request: Request, **extra):
    ctx = {
        "request": request,
        "app_title": "Jane",
        "app_icon": "🧠",
        "app_subtitle": "Your long-lived technical partner",
        "footer_label": "Jane · Project Ambient",
        "google_oauth_enabled": google_oauth_configured(),
    }
    ctx.update(extra)
    return ctx


def _read_announcements(since: Optional[str]) -> list[dict]:
    if not ANNOUNCEMENTS_PATH.exists():
        return []
    # Truncate announcements file if it exceeds 1MB to prevent unbounded growth
    try:
        if ANNOUNCEMENTS_PATH.stat().st_size > 1 * 1024 * 1024:
            lines = ANNOUNCEMENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            ANNOUNCEMENTS_PATH.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
    except Exception:
        pass
    try:
        since_dt = datetime.fromisoformat(since) if since else None
    except ValueError:
        since_dt = None
    rows: list[dict] = []
    with ANNOUNCEMENTS_PATH.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            created_at = payload.get("created_at") or payload.get("timestamp")
            if since_dt and created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                except ValueError:
                    created_dt = None
                if created_dt and created_dt <= since_dt:
                    continue
            rows.append(payload)
    return rows


# ─── Init ─────────────────────────────────────────────────────────────────────

_background_tasks: set[asyncio.Task] = set()  # prevent GC of fire-and-forget tasks


@app.on_event("startup")
async def startup():
    init_db()
    _auto_load_essences()
    # Start periodic reaper for stale Claude/Gemini sessions (prevents memory leaks)
    reaper = asyncio.create_task(_reap_stale_sessions_loop())
    _background_tasks.add(reaper)
    reaper.add_done_callback(_background_tasks.discard)
    _logger.info("Jane Web startup complete — database initialized, essences loaded, ready to serve")
    # Resume processing any unprocessed shared articles left from before a restart
    asyncio.create_task(_resume_shared_queue_if_needed())
    # Pre-warm gemma4:e4b — used by the prompt router for every request
    prewarm = asyncio.create_task(_prewarm_gemma4())
    _background_tasks.add(prewarm)
    prewarm.add_done_callback(_background_tasks.discard)
    # Start Standing Brain processes (3 tiers: light/medium/heavy)
    standing_brain_task = asyncio.create_task(_start_standing_brains())
    _background_tasks.add(standing_brain_task)
    standing_brain_task.add_done_callback(_background_tasks.discard)


async def _start_standing_brains():
    """Start the standing brain CLI process at service startup."""
    try:
        from jane.standing_brain import get_standing_brain_manager
        manager = get_standing_brain_manager()
        await manager.start()
        health = await manager.health_check()
        if health.get("alive"):
            _logger.info("Standing Brain alive: model=%s pid=%s turns=%d",
                          health["model"], health.get("pid"), health.get("turns", 0))
        else:
            _logger.warning("Standing Brain not alive after startup: %s", health)
    except Exception as exc:
        _logger.error("Standing Brain startup failed: %s", exc)


async def _prewarm_gemma4():
    """Pre-warm gemma4:e4b via ollama HTTP API with keep_alive=-1 (pinned).

    Using the HTTP API (not `ollama run`) lets us set keep_alive=-1, which
    keeps the model loaded in memory indefinitely instead of ollama's 5-min
    default idle timeout.
    """
    model = os.environ.get("GEMMA_ROUTER_MODEL", "gemma4:e4b")
    if ":" not in model:
        return
    _logger.info("Pre-warming Gemma4 router model: %s", model)
    try:
        import aiohttp
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False, "keep_alive": -1},
            ) as resp:
                await resp.read()
        _logger.info("Gemma4 router model %s pre-warmed (keep_alive=-1)", model)
    except Exception as e:
        _logger.warning("Gemma4 prewarm failed: %s", e)


async def _prewarm_ollama():
    """Legacy prewarm — no longer called at startup."""
    import subprocess
    model = os.environ.get("INTENT_CLASSIFIER_MODEL", "gemma4:e4b")
    if ":" not in model:
        return  # API model, no need to prewarm
    _logger.info("Pre-warming Ollama model: %s", model)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "run", model, "hi",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=60)
        _logger.info("Ollama model %s pre-warmed successfully", model)
    except Exception as exc:
        _logger.warning("Ollama pre-warm failed: %s", exc)


async def _reap_stale_sessions_loop():
    """Periodically reap stale Claude and Gemini persistent sessions to prevent memory leaks."""
    while True:
        await asyncio.sleep(600)  # every 10 minutes
        try:
            from jane.persistent_claude import get_claude_persistent_manager
            manager = get_claude_persistent_manager()
            reaped = await manager.reap_stale_sessions()
            if reaped:
                _logger.info("Reaped %d stale Claude sessions", reaped)
        except Exception as e:
            _logger.warning("Claude session reaper error (non-fatal): %s", e)
        # Also reap stale Gemini persistent sessions
        try:
            from jane.persistent_gemini import get_gemini_persistent_manager
            gm = get_gemini_persistent_manager(os.environ.get("VESSENCE_HOME", ""))
            gemini_reaped = await gm.reap_stale_sessions()
            if gemini_reaped:
                _logger.info("Reaped %d stale Gemini sessions", gemini_reaped)
        except Exception as e:
            _logger.warning("Gemini session reaper error (non-fatal): %s", e)
        # Also prune in-memory Jane proxy sessions
        try:
            from jane_web.jane_proxy import _prune_stale_sessions
            _prune_stale_sessions()
        except Exception as e:
            _logger.warning("Jane proxy session pruner error (non-fatal): %s", e)


@app.on_event("shutdown")
async def shutdown():
    """Clean up persistent workers to prevent zombie processes on restart.

    Uses force_shutdown_all() for Claude sessions to avoid deadlocking on
    the session lock (which may be held by an in-progress turn). Uses killpg()
    to kill entire process trees (Bun workers, tokio runtimes, etc.) instead
    of just the parent process.
    """
    _logger.info("Jane Web shutting down — cleaning up persistent workers...")

    # Claude: force-kill all subprocesses without acquiring locks
    try:
        from jane.persistent_claude import get_claude_persistent_manager
        killed = get_claude_persistent_manager().force_shutdown_all()
        _logger.info("Claude cleanup: killed %d processes", killed)
    except Exception as e:
        _logger.warning(f"Claude cleanup error (non-fatal): {e}")

    # Gemini: shutdown PTY sessions
    try:
        from jane.persistent_gemini import get_gemini_persistent_manager
        manager = get_gemini_persistent_manager(os.environ.get("VESSENCE_HOME", ""))
        for sid in list(getattr(manager, '_sessions', {}).keys()):
            try:
                await manager.end(sid)
            except Exception:
                pass
    except Exception as e:
        _logger.warning(f"Gemini cleanup error (non-fatal): {e}")

    # Standing Brain: kill all tiers in parallel
    try:
        from jane.standing_brain import get_standing_brain_manager
        await get_standing_brain_manager().shutdown()
    except Exception as e:
        _logger.warning(f"Standing Brain cleanup error (non-fatal): {e}")

    # Cancel background tasks (session reaper, etc.)
    for task in list(_background_tasks):
        task.cancel()
    _logger.info("Jane Web shutdown complete.")


def _auto_load_essences():
    """Scan ESSENCES_DIR and auto-load all valid essences on startup."""
    from agent_skills.essence_runtime import EssenceRuntime, CapabilityRegistry
    global _capability_registry
    _capability_registry = CapabilityRegistry()

    runtime = _get_essence_runtime()
    available = list_available_essences()
    loaded_names = []
    for e in available:
        try:
            state = load_essence(e["path"])
            _essence_states[e["name"]] = state
            # Also load into the runtime for orchestration
            try:
                runtime.load_essence(e["name"])
            except Exception:
                pass  # runtime may fail on chromadb import; non-fatal
            # Register capabilities
            caps = state.capabilities.get("provides", [])
            if caps:
                _capability_registry.register(e["name"], caps)
            loaded_names.append(e["name"])
            _logger.info("Auto-loaded essence '%s' (%s) — capabilities: %s",
                         e["name"], state.role_title, caps)
        except Exception as exc:
            _logger.warning("Failed to auto-load essence '%s': %s", e["name"], exc)
    _logger.info("Auto-loaded %d essences: %s", len(loaded_names), loaded_names)


def _get_essence_runtime():
    """Get or create the singleton EssenceRuntime."""
    try:
        from agent_skills.essence_runtime import EssenceRuntime
        return EssenceRuntime(TOOLS_DIR)
    except Exception as exc:
        _logger.warning("Could not initialize EssenceRuntime: %s", exc)
        return None


@app.get("/health")
async def health():
    brain = os.getenv("JANE_BRAIN", "gemini")
    return {"status": "ok", "service": "jane", "brain": brain}


@app.get("/sw.js")
async def service_worker():
    return FileResponse(str(STATIC_DIR / "chat-sw.js"), media_type="application/javascript")


@app.get("/manifest.webmanifest")
async def web_manifest():
    return FileResponse(str(STATIC_DIR / "jane.webmanifest"), media_type="application/manifest+json")


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def get_session_id(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE)


def _is_local_browser_access(request: Request) -> bool:
    host = (request.headers.get("host") or request.url.hostname or "").split(",")[0].strip().lower()
    host = host.split(":")[0]
    return host in ("localhost", "127.0.0.1", "::1")


def require_auth(request: Request):
    # Allow internal requests from localhost (prompt queue runner, cron jobs)
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost") or _is_local_browser_access(request):
        return request.query_params.get("session_id") or "internal"
    session_id = get_session_id(request)
    fp = device_fingerprint_from_request(request)
    if not session_id or not validate_session(session_id, fp):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id


def _default_user_id() -> str:
    allowed = [e.strip() for e in os.getenv("ALLOWED_GOOGLE_EMAILS", "").split(",") if e.strip()]
    if allowed:
        return allowed[0]
    user_name = os.getenv("USER_NAME", "").strip().lower()
    return "_".join(user_name.split()) if user_name else "user"


def get_trusted_device_cookie_id(request: Request) -> Optional[str]:
    return request.cookies.get(TRUSTED_DEVICE_COOKIE)


def get_or_bootstrap_session(request: Request) -> tuple[Optional[str], Optional[str]]:
    session_id = get_session_id(request)
    fp = device_fingerprint_from_request(request)
    if session_id and validate_session(session_id, fp):
        _logger.info(
            "Session bootstrap reused existing session=%s trusted_cookie=%s ip=%s",
            _session_log_id(session_id),
            bool(get_trusted_device_cookie_id(request)),
            _client_ip(request),
        )
        prewarm_session(session_id)
        return session_id, get_trusted_device_cookie_id(request)

    trusted_cookie_id = get_trusted_device_cookie_id(request)
    trusted_row = get_trusted_device_by_id(trusted_cookie_id) if trusted_cookie_id else None
    if trusted_row:
        session_id = create_session(
            trusted_row["fingerprint"],
            trusted=True,
            user_id=trusted_row["label"] or _default_user_id(),
        )
        _logger.info(
            "Session bootstrap created session=%s via trusted-cookie trusted_device=%s ip=%s",
            _session_log_id(session_id),
            trusted_row["id"],
            _client_ip(request),
        )
        prewarm_session(session_id)
        return session_id, trusted_row["id"]

    trusted_row = get_trusted_device_by_fingerprint(fp)
    if trusted_row:
        session_id = create_session(
            fp,
            trusted=True,
            user_id=trusted_row["label"] or _default_user_id(),
        )
        _logger.info(
            "Session bootstrap created session=%s via fingerprint-match trusted_device=%s ip=%s",
            _session_log_id(session_id),
            trusted_row["id"],
            _client_ip(request),
        )
        prewarm_session(session_id)
        return session_id, trusted_row["id"]

    if _is_local_browser_access(request):
        session_id = create_session(fp, trusted=False, user_id=_default_user_id())
        _logger.info(
            "Session bootstrap created local session=%s host=%s ip=%s",
            _session_log_id(session_id),
            request.headers.get("host", ""),
            _client_ip(request),
        )
        prewarm_session(session_id)
        return session_id, None

    _logger.info(
        "Session bootstrap found no authenticated session ip=%s trusted_cookie=%s",
        _client_ip(request),
        bool(trusted_cookie_id),
    )
    return None, None


def check_share_or_auth(request: Request, path: str):
    session_id = get_session_id(request)
    fp = device_fingerprint_from_request(request)
    if session_id and validate_session(session_id, fp):
        return True
    share_code = request.cookies.get("share_code")
    if share_code:
        share = validate_share(share_code)
        if share and (path.startswith(share["path"]) or share["path"] == "/"):
            return True
    raise HTTPException(status_code=401, detail="Not authenticated")


def is_android_webview_request(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "")
    return "VessencesAndroid/" in user_agent


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        try:
            from .jane_proxy import get_active_brain
        except ImportError:
            from jane_proxy import get_active_brain
        response = templates.TemplateResponse(
            "jane.html",
            {
                "request": request,
                "brain_label": get_active_brain(),
                "initial_session_id": session_id,
            },
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/share", response_class=HTMLResponse)
async def share_page(request: Request):
    return templates.TemplateResponse("login.html", _login_context(request, share_mode=True))


@app.get("/vault", response_class=HTMLResponse)
async def vault_page(request: Request):
    """Serve the vault file browser (previously at vault_web port 8080)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        response = templates.TemplateResponse(
            "app.html",
            {
                "request": request,
                "initial_tab": "vault",
                "android_webview": is_android_webview_request(request),
            },
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """Serve the Jane User Guide page."""
    return templates.TemplateResponse("guide.html", {"request": request})


@app.get("/architecture", response_class=HTMLResponse)
async def architecture_page(request: Request):
    """Serve the Jane Architecture deep-dive page."""
    return templates.TemplateResponse("architecture.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the Amber chat tab (previously at vault_web)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        response = templates.TemplateResponse(
            "app.html",
            {
                "request": request,
                "initial_tab": "chat",
                "android_webview": is_android_webview_request(request),
            },
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/essences", response_class=HTMLResponse)
async def essences_page(request: Request, _=Depends(require_auth)):
    return FileResponse(str(STATIC_DIR / "essences.html"), media_type="text/html")

@app.get("/worklog", response_class=HTMLResponse)
async def worklog_page(request: Request, _=Depends(require_auth)):
    return FileResponse(str(STATIC_DIR / "worklog.html"), media_type="text/html")

@app.get("/api/job-queue")
async def get_job_queue(_=Depends(require_auth)):
    """Return job queue as structured JSON for client-side rendering."""
    import subprocess as _sp
    try:
        r = _sp.run(
            [sys.executable, os.path.join(CODE_ROOT, "agent_skills", "show_job_queue.py")],
            capture_output=True, text=True, timeout=5,
        )
        return json.loads(r.stdout) if r.stdout.strip() else {"columns": [], "jobs": [], "count": 0}
    except Exception:
        return {"columns": [], "jobs": [], "count": 0}


@app.get("/api/job-queue/completed")
async def get_completed_jobs(_=Depends(require_auth)):
    """Return completed jobs as structured JSON for client-side rendering."""
    import subprocess as _sp
    try:
        r = _sp.run(
            [sys.executable, os.path.join(CODE_ROOT, "agent_skills", "show_job_queue.py"), "--completed"],
            capture_output=True, text=True, timeout=5,
        )
        return json.loads(r.stdout) if r.stdout.strip() else {"columns": [], "jobs": [], "count": 0}
    except Exception:
        return {"columns": [], "jobs": [], "count": 0}


@app.get("/briefing", response_class=HTMLResponse)
async def briefing_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse("briefing.html", {"request": request})


@app.post("/api/crash-report")
async def receive_crash_report(request: Request):
    body = await request.body()
    report = body.decode("utf-8", errors="replace")
    crash_file = Path(LOGS_DIR) / "android_crashes.log"
    with open(crash_file, "a") as f:
        f.write(f"\n{'='*60}\n{report}\n")
    _logger.error("Android crash report received:\n%s", report[:500])
    return {"status": "received"}


@app.post("/api/device-diagnostics")
async def receive_device_diagnostics(request: Request):
    """Receive diagnostic data from Android: wake word status, mic state, errors, scores, etc."""
    import json as _json
    body = await request.json()
    diag_file = Path(LOGS_DIR) / "android_diagnostics.jsonl"
    with open(diag_file, "a") as f:
        f.write(_json.dumps(body) + "\n")
    category = body.get("category", "unknown")
    message = body.get("message", "")
    _logger.info("Android diagnostic [%s]: %s", category, message[:200])
    return {"status": "received"}


@app.get("/api/device-diagnostics")
async def get_device_diagnostics(request: Request, _=Depends(require_auth), lines: int = 50):
    """Read recent diagnostics (most recent first)."""
    diag_file = Path(LOGS_DIR) / "android_diagnostics.jsonl"
    if not diag_file.exists():
        return {"diagnostics": []}
    import json as _json
    all_lines = diag_file.read_text().strip().split("\n")
    recent = all_lines[-lines:]
    recent.reverse()
    entries = []
    for line in recent:
        try:
            entries.append(_json.loads(line))
        except _json.JSONDecodeError:
            pass
    return {"diagnostics": entries}


@app.get("/settings/devices", response_class=HTMLResponse)
async def devices_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse("app.html", {"request": request, "initial_tab": "settings",
                                                    "android_webview": is_android_webview_request(request)})


@app.get("/downloads/{filename}")
async def download_release_artifact(filename: str):
    """Serve public release downloads (APK, docker packages, etc.)."""
    target = PUBLIC_RELEASE_DOWNLOADS.get(filename)
    # If not a static entry, check if it matches an installer glob pattern
    if not target or not target.exists() or not target.is_file():
        glob_pattern = _INSTALLER_GLOBS.get(filename)
        if glob_pattern:
            target = _find_latest(glob_pattern)
    # Dynamic APK resolution — versioned and unversioned APK filenames are
    # resolved at request time (reading version.json fresh) so a bump_android_version
    # deploy does not require a jane-web restart to serve the new file.
    if not target or not target.exists() or not target.is_file():
        apk_target = _resolve_android_apk_path(filename)
        if apk_target is not None:
            target = apk_target
    # Legacy generic APK fallback (any .apk filename sitting in the downloads dir).
    if (not target or not target.exists() or not target.is_file()) and filename.endswith(".apk"):
        candidate = MARKETING_DOWNLOADS_DIR / filename
        if candidate.exists() and candidate.is_file():
            target = candidate
    if not target or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    suffix = target.suffix.lower()
    media_type = {
        ".apk": "application/vnd.android.package-archive",
        ".zip": "application/zip",
        ".yml": "application/octet-stream",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        str(target),
        media_type=media_type,
        filename=filename,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ─── App Update API ───────────────────────────────────────────────────────────

# ─── App Settings API (synced between server and Android) ────────────────────

_APP_SETTINGS_PATH = os.path.join(VESSENCE_DATA_HOME, "data", "app_settings.json")


def _load_app_settings() -> dict:
    try:
        with open(_APP_SETTINGS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_app_settings(settings: dict):
    os.makedirs(os.path.dirname(_APP_SETTINGS_PATH), exist_ok=True)
    with open(_APP_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


# ─── Chat TTS API — XTTS-v2 audio for Jane's chat responses ─────────────────

def _split_tts_chunks(text: str, max_chars: int = 150) -> list[str]:
    """Split text into sentence-level chunks for XTTS-v2 (~20s max per chunk)."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if current and len(current) + len(s) + 1 <= max_chars:
            current += " " + s
        else:
            if current:
                chunks.append(current)
            if len(s) > max_chars:
                for part in re.split(r',\s*', s):
                    if current and len(current) + len(part) + 2 <= max_chars:
                        current += ", " + part
                    else:
                        if current:
                            chunks.append(current)
                        current = part
            else:
                current = s
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


# Limit TTS to 1 concurrent Docker container to prevent RAM/CPU exhaustion
_tts_semaphore = asyncio.Semaphore(1)

@app.post("/api/tts/generate")
async def generate_tts(request: Request, _=Depends(require_auth)):
    """Generate XTTS-v2 audio for text. Chunks by sentence, compresses to Opus/OGG.
    Body: {"text": "...", "speaker": "Barbora MacLean"}
    """
    body = await request.json()
    text = body.get("text", "").strip()
    speaker = body.get("speaker", "Barbora MacLean")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    import hashlib, wave, tempfile, shutil
    text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    cache_dir = os.path.join(VESSENCE_DATA_HOME, "cache", "tts")
    os.makedirs(cache_dir, exist_ok=True)
    ogg_path = os.path.join(cache_dir, f"{text_hash}.ogg")

    # Check cache (both ogg and legacy wav)
    if os.path.exists(ogg_path):
        return FileResponse(ogg_path, media_type="audio/ogg")
    legacy_wav = os.path.join(cache_dir, f"{text_hash}.wav")
    if os.path.exists(legacy_wav):
        return FileResponse(legacy_wav, media_type="audio/wav")

    gpu_flag = ["--gpus", "all"] if os.path.exists("/usr/bin/nvidia-smi") else []
    chunks = _split_tts_chunks(text[:1000])
    tmp_dir = tempfile.mkdtemp(prefix="tts_web_")

    try:
        chunk_wavs = []
        for i, chunk in enumerate(chunks):
            chunk_wav = os.path.join(tmp_dir, f"chunk_{i:03d}.wav")
            cmd = [
                "docker", "run", "--rm", *gpu_flag,
                "--memory=4g", "--cpus=2",
                "-e", "COQUI_TOS_AGREED=1",
                "-v", f"{tmp_dir}:/output",
                "ghcr.io/coqui-ai/tts:latest",
                "--text", chunk,
                "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
                "--speaker_idx", speaker,
                "--language_idx", "en",
                "--out_path", f"/output/chunk_{i:03d}.wav",
            ]
            async with _tts_semaphore:
                result = await asyncio.to_thread(
                    subprocess.run, cmd,
                    capture_output=True, text=True, timeout=120,
                )
            if result.returncode == 0 and os.path.exists(chunk_wav):
                chunk_wavs.append(chunk_wav)

        if not chunk_wavs:
            raise HTTPException(status_code=500, detail="TTS generation failed")

        # Concatenate WAV chunks
        combined_wav = os.path.join(tmp_dir, "combined.wav")
        with wave.open(chunk_wavs[0], 'rb') as first:
            params = first.getparams()
        with wave.open(combined_wav, 'wb') as out:
            out.setparams(params)
            for wp in chunk_wavs:
                with wave.open(wp, 'rb') as w:
                    out.writeframes(w.readframes(w.getnframes()))

        # Compress to Opus/OGG
        compress_result = await asyncio.to_thread(
            subprocess.run,
            ["ffmpeg", "-y", "-i", combined_wav, "-c:a", "libopus", "-b:a", "48k", ogg_path],
            capture_output=True, text=True, timeout=60,
        )
        if compress_result.returncode == 0 and os.path.exists(ogg_path):
            return FileResponse(ogg_path, media_type="audio/ogg")

        # Fall back to serving uncompressed WAV if ffmpeg fails
        shutil.copy2(combined_wav, legacy_wav)
        return FileResponse(legacy_wav, media_type="audio/wav")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TTS generation timed out")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/app/settings")
async def get_app_settings(_=Depends(require_auth)):
    """Get synced app settings. Android polls this on startup."""
    return JSONResponse(_load_app_settings())


@app.put("/api/app/settings")
async def update_app_settings(request: Request, _=Depends(require_auth)):
    """Update app settings. Jane can call this to change user preferences remotely."""
    body = await request.json()
    current = _load_app_settings()
    current.update(body)
    _save_app_settings(current)
    return JSONResponse({"ok": True, "settings": current})


@app.post("/api/app/installed")
async def report_app_installed(request: Request):
    """Called by the Android app after installing a new version. Logs to work log."""
    try:
        body = await request.json()
        version = body.get("version_name", "unknown")
        _log_work_activity(f"Android app updated to v{version}", category="release")
    except Exception:
        pass
    return JSONResponse({"ok": True})


@app.get("/api/app/latest-version")
async def latest_app_version():
    # Read version.json fresh each time so builds are picked up without server restart
    vdata = _json.loads((CODE_ROOT / "version.json").read_text())
    version_name = vdata["version_name"]
    version_code = vdata["version_code"]
    apk_path = MARKETING_DOWNLOADS_DIR / f"vessences-android-v{version_name}.apk"
    # Guard: don't advertise a version whose APK hasn't been deployed yet.
    # If the file is missing, walk back to the newest APK that actually exists.
    if not apk_path.exists():
        existing = sorted(
            MARKETING_DOWNLOADS_DIR.glob("vessences-android-v*.apk"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if existing:
            version_name = existing[0].stem[len("vessences-android-v"):]
            # version_code from version.json may be ahead — use file-based name only
        else:
            # No APK at all; return version info without a usable download URL
            return {"version_code": version_code, "version_name": version_name, "download_url": None, "changelog": ""}
    return {
        "version_code": version_code,
        "version_name": version_name,
        "download_url": f"/downloads/vessences-android-v{version_name}.apk",
        "changelog": "",
    }


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.get("/auth/google")
async def login_google(request: Request):
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this deployment.")
    redirect_uri = build_external_url(
        request,
        str(request.app.url_path_for("auth_google_callback")),
        "JANE_PUBLIC_BASE_URL",
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request):
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this deployment.")
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="OAuth error")
    user_info = token.get("userinfo", {})
    email = user_info.get("email", "")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    if not is_device_trusted(fp):
        trusted_device_id = register_trusted_device(fp, email)
    else:
        trusted_row = get_trusted_device_by_fingerprint(fp)
        trusted_device_id = trusted_row["id"] if trusted_row else register_trusted_device(fp, email)
    session_id = create_session(fp, trusted=True, user_id=email)
    prewarm_session(session_id)
    resp = RedirectResponse(url="/")
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                    max_age=60 * 60 * 24 * 30)  # 30 days
    resp.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                    max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/api/auth/google-token")
async def auth_google_token(request: Request):
    """Accept a Google ID token from native Android apps and create a session."""
    body = await request.json()
    id_token_str = body.get("id_token", "")
    if not id_token_str:
        raise HTTPException(status_code=400, detail="id_token is required")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), client_id
        )
        email = idinfo.get("email", "")
    except Exception as exc:
        _logger.error("Google ID token verification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid Google ID token: {exc}")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    if not is_device_trusted(fp):
        trusted_device_id = register_trusted_device(fp, email)
    else:
        trusted_row = get_trusted_device_by_fingerprint(fp)
        trusted_device_id = trusted_row["id"] if trusted_row else register_trusted_device(fp, email)
    session_id = create_session(fp, trusted=True, user_id=email)
    prewarm_session(session_id)
    resp = JSONResponse({"ok": True, "session_id": session_id, "trusted_device_id": trusted_device_id})
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                    max_age=60 * 60 * 24 * 30)
    resp.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                    max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/api/auth/verify-share")
async def verify_share(request: Request, body: dict, response: Response):
    code = body.get("code", "")
    share = validate_share(code)
    if not share:
        return JSONResponse({"ok": False, "error": "Invalid share code"}, status_code=400)
    response.set_cookie("share_code", code, httponly=True, samesite="lax")
    return {"ok": True, "path": share["path"]}


@app.post("/api/auth/verify-otp")
async def verify_totp_login(request: Request, body: dict):
    code = (body.get("code") or "").strip()
    if not code:
        return JSONResponse({"ok": False, "error": "Code required."}, status_code=400)

    ok, error = verify_otp(code, request.client.host)
    if not ok:
        return JSONResponse({"ok": False, "error": error or "Invalid code."}, status_code=400)

    fp = device_fingerprint_from_request(request)
    user_id = _default_user_id()
    trusted_row = get_trusted_device_by_fingerprint(fp)
    trusted_device_id = trusted_row["id"] if trusted_row else register_trusted_device(fp, user_id)
    session_id = create_session(fp, trusted=True, user_id=user_id)
    prewarm_session(session_id)

    response = JSONResponse({"ok": True})
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                        max_age=60 * 60 * 24 * 30)
    response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                        max_age=60 * 60 * 24 * 30)
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    session_id = get_session_id(request)
    if session_id:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    resp.delete_cookie(TRUSTED_DEVICE_COOKIE)
    return resp


@app.get("/api/auth/devices")
async def list_devices(_=Depends(require_auth)):
    return get_trusted_devices()


@app.delete("/api/auth/devices/{device_id}")
async def delete_device(device_id: str, _=Depends(require_auth)):
    revoke_device(device_id)
    return {"ok": True}


@app.post("/api/auth/check")
async def check_auth(request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    response = JSONResponse({"authenticated": bool(session_id)})
    if session_id and get_session_id(request) != session_id:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
        response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    return response


@app.post("/api/auth/is-new-device")
async def is_new_device(request: Request):
    fp = device_fingerprint_from_request(request)
    return {"new_device": not is_device_trusted(fp)}


@app.get("/api/jane/announcements")
async def get_announcements(since: Optional[str] = None, _=Depends(require_auth)):
    return {"items": _read_announcements(since)}


# ─── Brain Model Settings ────────────────────────────────────────────────────

_AVAILABLE_MODELS = {
    "claude": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openai": ["gpt-5.4-mini", "gpt-5.4", "gpt-4.1-mini", "gpt-4.1", "o3"],
}

_DEFAULT_MODEL = {
    "claude": "claude-opus-4-6",
    "gemini": "gemini-2.5-pro",
    "openai": "gpt-5.4",
}

_ENV_VAR_FOR_MODEL = {
    "claude": "JANE_MODEL_CLAUDE",
    "gemini": "JANE_MODEL_GEMINI",
    "openai": "JANE_MODEL_OPENAI",
}


@app.get("/api/settings/models")
async def get_model_settings(_=Depends(require_auth)):
    """Return current model config, available options, and 3-tier architecture."""
    provider = os.environ.get("JANE_BRAIN", "claude").lower()
    default = _DEFAULT_MODEL.get(provider, _DEFAULT_MODEL["claude"])
    env_var = _ENV_VAR_FOR_MODEL.get(provider, _ENV_VAR_FOR_MODEL["claude"])
    legacy_var = f"BRAIN_HEAVY_{provider.upper()}"
    current = os.environ.get(env_var) or os.environ.get(legacy_var) or default

    # 4-Tier Architecture Information
    from jane.config import SMART_MODEL, CHEAP_MODEL, LOCAL_LLM_MODEL
    
    # Heuristic for the new tiers based on existing config
    # Orchestrator = current (the one you switch)
    # Agent = SMART_MODEL (the specialized one)
    # Utility = CHEAP_MODEL (the background one)
    # Local = LOCAL_LLM_MODEL (Ollama)
    
    tiers = [
        {"tier": "Orchestrator", "role": "The Primary Brain (Reasoning, Code)", "model": current},
        {"tier": "Agent", "role": "The Specialist (Research, Memory)", "model": SMART_MODEL},
        {"tier": "Utility", "role": "The Worker (Archival, Triage)", "model": CHEAP_MODEL},
        {"tier": "Local", "role": "Privacy & Speed (Local Processing)", "model": LOCAL_LLM_MODEL},
    ]

    return {
        "provider": provider,
        "model": {"current": current, "default": default, "env_var": env_var},
        "available_models": _AVAILABLE_MODELS,
        "tiers": tiers,
    }


@app.post("/api/settings/models")
async def save_model_settings(request: Request, _=Depends(require_auth)):
    """Save model selection to .env and restart the standing brain."""
    body = await request.json()
    provider = os.environ.get("JANE_BRAIN", "claude").lower()
    env_var = _ENV_VAR_FOR_MODEL.get(provider, _ENV_VAR_FOR_MODEL["claude"])

    model = body.get("model")
    if not model:
        return {"ok": False, "error": "No model specified"}

    # Update in-process env
    os.environ[env_var] = model

    # Write to .env file
    env_path = ENV_FILE_PATH
    lines = []
    if os.path.exists(env_path):
        async with aiofiles.open(env_path, "r") as f:
            lines = (await f.read()).splitlines()

    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key == env_var:
                new_lines.append(f"{env_var}={model}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{env_var}={model}")

    async with aiofiles.open(env_path, "w") as f:
        await f.write("\n".join(new_lines) + "\n")

    # Restart the standing brain so it picks up the new model
    try:
        from jane.standing_brain import get_standing_brain_manager
        manager = get_standing_brain_manager()
        if manager._started:
            await manager.shutdown()
            await manager.start()
            logger.info("Standing brain restarted with model=%s after settings change", model)
    except Exception:
        logger.exception("Failed to restart standing brain after model change")

    return {"ok": True, "model": model}


# ─── Live Broadcast SSE ──────────────────────────────────────────────────────

@app.get("/api/jane/live")
async def jane_live_stream(request: Request):
    """SSE endpoint: broadcasts summarized progress when Jane is working on another session."""
    from jane_web.broadcast import broadcast_manager

    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = get_session_user(session_id) or _default_user_id()

    q = await broadcast_manager.subscribe(user_id)

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield event.to_json() + "\n"
                except asyncio.TimeoutError:
                    # Send keepalive to prevent proxy/browser timeout
                    yield json.dumps({"type": "keepalive"}) + "\n"
        finally:
            await broadcast_manager.unsubscribe(user_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jane/prefetch-memory")
async def prefetch_memory(request: Request):
    """Pre-fetch memory context while user is idle. Cached for 60s.

    Fire-and-forget: starts a background query and returns immediately.
    When the user sends their first message, the cached result is used as
    memory_summary_fallback, skipping the ChromaDB round-trip.
    """
    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    run_prefetch_memory(session_id)
    return {"status": "ok", "cached": True}


# ─── Files API (shared vault) ─────────────────────────────────────────────────

_MIME_TO_SUBDIR = {
    "image": "images",
    "audio": "audio",
    "video": "video",
}


def _route_subdir(mime: str) -> str:
    if mime == "application/pdf":
        return "pdf"
    top = mime.split("/")[0]
    return _MIME_TO_SUBDIR.get(top, "documents")

@app.get("/api/files")
async def list_root(
    request: Request,
    offset: int = 0,
    limit: int = 0,
    _=Depends(require_auth),
):
    return _paginate_listing(list_directory(""), offset, limit)


@app.get("/api/files/list/{path:path}")
async def list_path(
    path: str,
    request: Request,
    offset: int = 0,
    limit: int = 0,
    _=Depends(require_auth),
):
    return _paginate_listing(list_directory(path), offset, limit)


def _paginate_listing(listing: dict, offset: int, limit: int) -> dict:
    """Apply optional offset/limit pagination to a directory listing.
    When limit <= 0, return the full listing (backwards compatible).
    Pagination applies to files only; folders are always returned in full.
    """
    if limit <= 0:
        return listing
    if "error" in listing:
        return listing
    files = listing.get("files", [])
    total_files = len(files)
    paginated_files = files[offset:offset + limit]
    listing["files"] = paginated_files
    listing["total_files"] = total_files
    listing["offset"] = offset
    listing["limit"] = limit
    return listing


@app.get("/api/files/meta/{path:path}")
async def file_meta(path: str, request: Request, _=Depends(require_auth)):
    return get_file_metadata(path)


@app.patch("/api/files/description/{path:path}")
async def update_file_description(path: str, body: dict, _=Depends(require_auth)):
    ok = update_description(path, body.get("description", ""))
    return {"ok": ok}


@app.get("/api/files/thumbnail/{path:path}")
async def thumbnail(path: str, request: Request):
    check_share_or_auth(request, path)
    data = generate_thumbnail(path)
    if not data:
        raise HTTPException(status_code=404)
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/files/serve/{path:path}")
async def serve_file(path: str, request: Request):
    check_share_or_auth(request, path)
    try:
        target = safe_vault_path(path)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    mime = get_mime(target.name)
    range_header = request.headers.get("range")
    if range_header:
        return _range_response(target, mime, range_header)
    headers = {}
    if mime and mime.startswith("image/"):
        headers["Cache-Control"] = "public, max-age=86400, immutable"
    return FileResponse(str(target), media_type=mime, headers=headers)


def _range_response(path: Path, mime: str, range_header: str):
    size = path.stat().st_size
    start, end = 0, size - 1
    try:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0]) if ranges[0] else 0
        end = int(ranges[1]) if ranges[1] else size - 1
    except Exception:
        pass
    end = min(end, size - 1)
    length = end - start + 1

    def iter_file():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(iter_file(), status_code=206, media_type=mime, headers={
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    })


@app.get("/api/files/changes")
async def file_changes(_=Depends(require_auth)):
    return {"last_change": get_last_change_timestamp()}


@app.get("/api/files/find")
async def find_file(name: str, _=Depends(require_auth)):
    name = os.path.basename(name)
    for root, dirs, files in os.walk(VAULT_DIR):
        if name in files:
            rel = os.path.relpath(os.path.join(root, name), VAULT_DIR)
            return {"path": rel}
    raise HTTPException(status_code=404, detail="File not found in vault")


# ── File type extension map ──────────────────────────────────────────────────
_FILE_TYPE_EXTENSIONS = {
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "document": {".pdf", ".doc", ".docx", ".txt", ".md"},
}

def _detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for ftype, exts in _FILE_TYPE_EXTENSIONS.items():
        if ext in exts:
            return ftype
    return "other"


@app.get("/api/files/search")
async def search_files(q: str, type: Optional[str] = None, _=Depends(require_auth)):
    """Search vault files by name and ChromaDB description."""
    if not q or not q.strip():
        return {"results": []}

    query = q.strip().lower()
    results_map: dict[str, dict] = {}  # keyed by relative path

    # 1. Walk vault and match filenames
    type_exts = _FILE_TYPE_EXTENSIONS.get(type) if type else None
    for root, _dirs, files in os.walk(VAULT_DIR):
        for fname in files:
            if fname.startswith("."):
                continue
            if query in fname.lower():
                ext = os.path.splitext(fname)[1].lower()
                if type_exts and ext not in type_exts:
                    continue
                rel = os.path.relpath(os.path.join(root, fname), VAULT_DIR)
                ftype = _detect_file_type(fname)
                results_map[rel] = {
                    "name": fname,
                    "path": rel,
                    "type": ftype,
                    "description": "",
                    "serve_url": f"/api/files/serve/{rel}",
                }

    # 2. Query ChromaDB for file descriptions
    try:
        _skills_dir = os.path.join(
            os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence")),
            "agent_skills",
        )
        if _skills_dir not in sys.path:
            sys.path.insert(0, _skills_dir)
        from memory_retrieval import _query_collection
        vector_db = os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        ) + "/vector_db"
        for collection_name in ("vault_files", "facts"):
            try:
                docs, metas, _dists = _query_collection(vector_db, collection_name, q, 20)
                for doc, meta in zip(docs, metas):
                    # Try to extract a path from metadata
                    fpath = (meta or {}).get("path", "") or (meta or {}).get("file", "") or ""
                    if not fpath:
                        continue
                    # Make relative to vault
                    if os.path.isabs(fpath):
                        try:
                            fpath = os.path.relpath(fpath, VAULT_DIR)
                        except ValueError:
                            continue
                    fname = os.path.basename(fpath)
                    ftype = _detect_file_type(fname)
                    if type_exts:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in type_exts:
                            continue
                    if fpath not in results_map:
                        # Verify the file actually exists
                        full = os.path.join(VAULT_DIR, fpath)
                        if not os.path.isfile(full):
                            continue
                        results_map[fpath] = {
                            "name": fname,
                            "path": fpath,
                            "type": ftype,
                            "description": (doc or "")[:200],
                            "serve_url": f"/api/files/serve/{fpath}",
                        }
                    else:
                        # Enrich existing result with description
                        if doc and not results_map[fpath]["description"]:
                            results_map[fpath]["description"] = (doc or "")[:200]
                break  # If first collection worked, don't try fallback
            except Exception:
                continue
    except Exception:
        pass  # ChromaDB not available — filename results only

    results = list(results_map.values())[:20]
    return {"results": results}


@app.get("/api/files/play/{path:path}")
async def play_audio_file(path: str, _=Depends(require_auth)):
    """Serve an audio file with appropriate headers for streaming playback."""
    try:
        target = safe_vault_path(path)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    mime = get_mime(target.name)
    return FileResponse(
        str(target),
        media_type=mime,
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/api/files/content/{path:path}")
async def get_file_content(path: str, _=Depends(require_auth)):
    try:
        target = safe_vault_path(path)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    if not is_text(target.name):
        raise HTTPException(status_code=400, detail="Not a text file")
    if target.stat().st_size > TEXT_SIZE_LIMIT:
        raise HTTPException(status_code=413, detail="File too large to edit in browser")
    async with aiofiles.open(target, "r", encoding="utf-8", errors="replace") as f:
        content = await f.read()
    return {"content": content}


@app.put("/api/files/content/{path:path}")
async def save_file_content(path: str, body: dict, _=Depends(require_auth)):
    try:
        target = safe_vault_path(path)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    if not is_text(target.name):
        raise HTTPException(status_code=400, detail="Not a text file")
    async with aiofiles.open(target, "w", encoding="utf-8") as f:
        await f.write(body.get("content", ""))
    with get_db() as conn:
        conn.execute("INSERT INTO file_changes DEFAULT VALUES")
    return {"ok": True}


@app.post("/api/files/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    destination: str = Form(""),
    descriptions_json: str = Form("[]"),
    _=Depends(require_auth),
):
    vault_root = Path(VAULT_DIR)
    hash_index_path = vault_root / ".hash_index.json"
    try:
        descriptions = json.loads(descriptions_json or "[]")
    except json.JSONDecodeError:
        descriptions = []

    try:
        with open(hash_index_path) as f:
            hash_index = json.load(f)
    except Exception:
        hash_index = {}

    results = []
    for index, upload in enumerate(files):
        data = await upload.read()
        file_hash = hashlib.sha256(data).hexdigest()

        if file_hash in hash_index:
            existing = hash_index[file_hash]
            results.append({
                "name": upload.filename,
                "status": "duplicate",
                "existing_path": existing.get("path", ""),
            })
            continue

        if destination:
            subdir = destination.strip("/")
        else:
            mime = upload.content_type or get_mime(upload.filename or "")
            subdir = _route_subdir(mime)
        description = ""
        if index < len(descriptions):
            description = str(descriptions[index] or "").strip()
        is_image_upload = mime.startswith("image/")
        if is_image_upload and not description:
            raise HTTPException(status_code=400, detail="Image uploads require a description.")

        dest_dir = vault_root / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        if is_image_upload:
            safe_name = make_descriptive_filename(upload.filename or "upload", description)
        else:
            safe_name = Path(upload.filename or "upload").name
        dest_path = dest_dir / safe_name
        if dest_path.exists():
            stem, suffix = dest_path.stem, dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        with open(dest_path, "wb") as f:
            f.write(data)

        rel_path = str(dest_path.relative_to(vault_root))
        hash_index[file_hash] = {
            "filename": dest_path.name,
            "path": rel_path,
            "description": description,
        }
        upsert_file_index_entry(rel_path, description, mime, updated_by="jane_web_upload")

        try:
            subprocess.run([
                ADK_VENV_PYTHON,
                ADD_FACT_SCRIPT,
                f"File uploaded via web UI: {dest_path.name} saved to vault/{subdir}/",
                "--topic", "vault", "--subtopic", "upload",
            ], timeout=10, capture_output=True)
        except Exception:
            pass

        results.append({
            "name": upload.filename,
            "saved_name": dest_path.name,
            "status": "ok",
            "path": rel_path,
            "subdir": subdir,
            "description": description,
        })

    try:
        with open(hash_index_path, "w") as f:
            json.dump(hash_index, f)
    except Exception:
        pass

    with get_db() as conn:
        conn.execute("INSERT INTO file_changes DEFAULT VALUES")

    uploaded_names = [r["saved_name"] for r in results if r.get("status") == "ok"]
    if uploaded_names:
        _log_work_activity(f"File upload: {', '.join(uploaded_names[:3])}", category="file_upload")

    return {"results": results}


@app.post("/api/files/upload/single")
async def upload_single_file(
    request: Request,
    file: UploadFile = File(...),
):
    """Simple single-file upload for Android — returns a serveable URL."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    vault_root = Path(VAULT_DIR)
    data = await file.read()
    mime = file.content_type or get_mime(file.filename or "")
    subdir = "working_files/android_uploads"
    dest_dir = vault_root / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "upload").name
    dest_path = dest_dir / safe_name
    if dest_path.exists():
        stem, suffix = dest_path.stem, dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    with open(dest_path, "wb") as f:
        f.write(data)

    rel_path = str(dest_path.relative_to(vault_root))

    # Index in ChromaDB so Jane and memory system can find the file
    try:
        from vault_web.files import upsert_file_index_entry
        upsert_file_index_entry(rel_path, f"File uploaded from Android: {dest_path.name}", mime, updated_by="android_upload")
    except Exception:
        pass

    # Save to memory
    try:
        import subprocess as _sp
        _sp.run([
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "agent_skills" / "add_fact.py"),
            f"File uploaded from Android: {dest_path.name} saved to vault/{subdir}/",
            "--topic", "vault", "--subtopic", "upload",
        ], timeout=10, capture_output=True)
    except Exception:
        pass

    response = JSONResponse({
        "file_url": f"/api/files/serve/{rel_path}",
        "filename": dest_path.name,
        "path": rel_path,
        "mime": mime,
    })
    if get_session_id(request) != session_id:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
        response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    return response


# ─── Share API ────────────────────────────────────────────────────────────────

@app.get("/api/shares")
async def get_shares(_=Depends(require_auth)):
    return list_shares()


@app.post("/api/shares")
async def new_share(body: dict, _=Depends(require_auth)):
    code = create_share(body.get("path", ""), body.get("recipient", "guest"))
    return {"ok": True, "code": code}


@app.delete("/api/shares/{share_id}")
async def delete_share(share_id: str, _=Depends(require_auth)):
    revoke_share(share_id)
    return {"ok": True}


# ─── Playlist API ─────────────────────────────────────────────────────────────

@app.get("/api/playlists")
async def get_playlists(_=Depends(require_auth)):
    return list_playlists()


@app.get("/api/playlists/{playlist_id}")
async def get_single_playlist(playlist_id: str, _=Depends(require_auth)):
    p = get_playlist(playlist_id)
    if not p:
        raise HTTPException(status_code=404)
    return p


@app.post("/api/playlists")
async def new_playlist(body: dict, _=Depends(require_auth)):
    return create_playlist(body.get("name", "New Playlist"), body.get("tracks", []))


@app.put("/api/playlists/{playlist_id}")
async def update_playlist_route(playlist_id: str, body: dict, _=Depends(require_auth)):
    p = update_playlist(playlist_id, body.get("name"), body.get("tracks"))
    if not p:
        raise HTTPException(status_code=404)
    return p


@app.delete("/api/playlists/{playlist_id}")
async def delete_playlist_route(playlist_id: str, _=Depends(require_auth)):
    delete_playlist(playlist_id)
    return {"ok": True}


def _cleanup_temporary_playlists():
    """Delete all Jane-generated temporary playlists from the database.

    Jane creates playlists named "Random Mix" or "Playing: <query>" via voice
    commands. These are meant to be ephemeral — played once and discarded.
    Without cleanup they accumulate indefinitely. This function purges them
    before a new one is created so there's never more than one temporary
    playlist alive at a time.

    User-created playlists (saved/renamed via the Music Playlist essence)
    are never touched because they don't match the naming pattern.
    """
    try:
        from vault_web.playlists import list_playlists, delete_playlist as _del
        for p in list_playlists():
            name = p.get("name", "")
            if name == "Random Mix" or name.startswith("Playing:"):
                _del(p["id"])
    except Exception as e:
        _logger.warning("temporary playlist cleanup failed: %s", e)


def create_music_playlist_from_query(query: str) -> dict | None:
    """Search vault music by query and create a temporary playlist.

    Returns playlist dict {"id", "name", "tracks", ...} or None if no matches.
    Shared by /api/music/play endpoint and jane_proxy gemma4 music handler.
    Cleans up any prior temporary playlists first so they don't accumulate.
    """
    import glob as _glob, random as _random

    _cleanup_temporary_playlists()
    q = (query or "").strip().lower()
    vault_music = Path(os.environ.get("VAULT_HOME", Path.home() / "ambient" / "vault")) / "Music"

    all_files = sorted(_glob.glob(str(vault_music / "**" / "*.mp3"), recursive=True))
    if not all_files:
        return None

    if q in ("random", "anything", "something", "a song", "music", "random song",
             "some music", "something random"):
        selected = _random.sample(all_files, min(10, len(all_files)))
        playlist_name = "Random Mix"
    else:
        # Tier 1: full query as substring of filename
        selected = [f for f in all_files if q in f.lower().split("/")[-1].lower()]
        if not selected:
            # Tier 2: word match — but filter out stopwords that match everything.
            # "songs by foo fighter" should match on "foo" and "fighter", NOT "by" or "songs".
            _stopwords = {"a", "an", "the", "by", "of", "in", "on", "to", "for", "and", "or",
                          "is", "it", "my", "me", "we", "do", "have", "any", "some", "from",
                          "song", "songs", "music", "play", "playing", "listen", "track", "tracks",
                          "album", "artist", "something", "anything", "like", "want", "hear"}
            words = [w for w in q.split() if w not in _stopwords and len(w) > 1]
            if words:
                # Require ALL remaining words to match (AND logic), not ANY (OR logic).
                # "foo fighter" → file must contain both "foo" AND "fighter".
                selected = [f for f in all_files
                            if all(w in f.lower().split("/")[-1].lower() for w in words)]
            if not selected and words:
                # Tier 3: OR logic as last resort, but only with content words
                selected = [f for f in all_files
                            if any(w in f.lower().split("/")[-1].lower() for w in words)]
        if not selected:
            return None
        playlist_name = f"Playing: {q.title()}"

    tracks = []
    for filepath in selected:
        # rel_path is relative to VAULT_DIR (e.g., "Music/Coldplay/Clocks.mp3")
        # so that /api/files/serve/{rel_path} resolves correctly server-side.
        rel_path = str(Path(filepath).relative_to(vault_music.parent))
        filename = Path(filepath).stem
        tracks.append({"path": rel_path, "title": filename})

    playlist = create_playlist(playlist_name, tracks)
    playlist["temporary"] = True
    return playlist


@app.post("/api/music/play")
async def music_play(body: dict, _=Depends(require_auth)):
    """Search vault music by query and create a temporary playlist.

    Body: {"query": "the scientist"} or {"query": "shakira"} or {"query": "random"}
    Returns: {"playlist_id": "...", "name": "...", "tracks": [...], "temporary": true}
    """
    query = (body.get("query") or "").strip()
    playlist = create_music_playlist_from_query(query)
    if playlist is None:
        raise HTTPException(status_code=404, detail=f"No tracks matching '{query}'")
    return playlist


# ─── Jane Chat API ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: str
    file_context: Optional[str] = None
    platform: Optional[str] = None  # "web", "android", "cli"
    tts_enabled: Optional[bool] = False


class SessionControl(BaseModel):
    session_id: str


async def _handle_jane_chat(body: ChatMessage, request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        _logger.warning(
            "Rejected jane chat request: no authenticated session body_session=%s ip=%s",
            _session_log_id(body.session_id),
            _client_ip(request),
        )
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = get_session_user(session_id) or _default_user_id()
    _logger.info(
        "Accepted jane chat request session=%s user=%s msg_len=%d file_ctx=%s body_session=%s",
        _session_log_id(session_id),
        user_id,
        len(body.message or ""),
        bool(body.file_context),
        _session_log_id(body.session_id),
    )
    result = await send_message(user_id, session_id, body.message, body.file_context, platform=body.platform, tts_enabled=body.tts_enabled or False)
    response = JSONResponse({"response": result.get("text", ""), "files": result.get("files", [])})
    if get_session_id(request) != session_id:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
        response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    return response


@app.post("/api/jane/chat")
async def jane_chat(body: ChatMessage, request: Request):
    return await _handle_jane_chat(body, request)


@app.post("/api/jane/session/end")
async def jane_end_session(body: SessionControl, request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    _logger.info(
        "Ending Jane session active_session=%s body_session=%s ip=%s",
        _session_log_id(session_id),
        _session_log_id(body.session_id),
        _client_ip(request),
    )
    end_session(session_id)
    response = JSONResponse({"ok": True})
    if get_session_id(request) != session_id:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
        response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    return response


# ─── Provider Switch API ──────────────────────────────────────────────────────

class SwitchProviderRequest(BaseModel):
    provider: str

@app.post("/api/jane/switch-provider")
async def switch_provider(body: SwitchProviderRequest, request: Request):
    """Switch the active LLM provider at runtime (kill old CLI, start new one)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_provider = body.provider.lower().strip()
    if new_provider not in ("claude", "gemini", "openai"):
        return JSONResponse({"ok": False, "error": f"Unknown provider: {new_provider}"}, status_code=400)

    from jane.standing_brain import get_standing_brain_manager
    manager = get_standing_brain_manager()

    _logger.info("Provider switch requested: → %s (session=%s, ip=%s)",
                 new_provider, _session_log_id(session_id), _client_ip(request))

    result = await manager.switch_provider(new_provider)

    if result.get("ok") and result.get("needs_auth"):
        # Return info so the frontend can trigger the OAuth flow
        result["auth_endpoint"] = "/api/cli-login"
        result["auth_status_endpoint"] = "/api/cli-login/status"

    return JSONResponse(result)


@app.get("/api/jane/current-provider")
async def current_provider():
    """Return the currently active provider, model, and all available providers."""
    import shutil
    from jane.standing_brain import get_standing_brain_manager, _PROVIDER
    manager = get_standing_brain_manager()
    health = await manager.health_check()
    available = []
    for prov, cli_name in [("claude", "claude"), ("gemini", "gemini"), ("openai", "codex")]:
        installed = shutil.which(cli_name) is not None
        available.append({"provider": prov, "installed": installed, "active": prov == _PROVIDER})
    return JSONResponse({
        "provider": _PROVIDER,
        "model": health.get("model", "unknown"),
        "alive": health.get("alive", False),
        "available": available,
    })


# ─── Generic Essence Tool API ─────────────────────────────────────────────────
# Allows any essence's custom_tools.py functions to be called via API
# without hardcoding routes per essence.

@app.post("/api/essence/{essence_name}/tool/{tool_name}")
async def call_essence_tool(essence_name: str, tool_name: str, request: Request, _=Depends(require_auth)):
    """Generic endpoint to invoke any essence tool by name."""
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    search_dirs = [
        os.environ.get("TOOLS_DIR", os.path.join(ambient_base, "tools")),
        os.path.join(ambient_base, "essences"),
    ]
    tools_path = os.path.join(search_dirs[0], essence_name.lower().replace(" ", "_"), "functions", "custom_tools.py")

    # Try common folder name patterns across both dirs
    if not os.path.isfile(tools_path):
        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for entry in os.listdir(search_dir):
                manifest = os.path.join(search_dir, entry, "manifest.json")
                if os.path.isfile(manifest):
                    try:
                        with open(manifest) as f:
                            m = json.load(f)
                        if m.get("essence_name", "").lower() == essence_name.lower():
                            tools_path = os.path.join(search_dir, entry, "functions", "custom_tools.py")
                            break
                    except Exception:
                        continue
            if os.path.isfile(tools_path):
                break

    if not os.path.isfile(tools_path):
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found or has no tools")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    args_json = json.dumps(body) if body else ""
    cmd = [python_bin, tools_path, tool_name]
    if args_json:
        cmd.append(args_json)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                cwd=os.path.dirname(tools_path))
        if result.returncode != 0:
            return JSONResponse({"status": "error", "message": result.stderr[:300]}, status_code=500)
        return JSONResponse(json.loads(result.stdout))
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok", "output": result.stdout.strip()})
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Tool execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dynamic essence page serving
@app.get("/essence/{essence_name}", response_class=HTMLResponse)
async def serve_essence_page(essence_name: str, request: Request, _=Depends(require_auth)):
    """Serve an essence's UI — or redirect to Jane's chat for essence-type items."""
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    search_dirs = [
        os.environ.get("TOOLS_DIR", os.path.join(ambient_base, "tools")),
        os.path.join(ambient_base, "essences"),
    ]
    # Find the essence folder across both directories
    template_path = None
    essence_folder_name = None
    essence_type = "tool"
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for entry in os.listdir(search_dir):
            manifest = os.path.join(search_dir, entry, "manifest.json")
            if os.path.isfile(manifest):
                try:
                    with open(manifest) as f:
                        m = json.load(f)
                    if m.get("essence_name", "").lower() == essence_name.lower():
                        essence_type = m.get("type", "tool")
                        essence_folder_name = entry
                        candidate = os.path.join(search_dir, entry, "ui", "template.html")
                        if os.path.isfile(candidate):
                            template_path = candidate
                        break
                except Exception:
                    continue
        if essence_folder_name:
            break

    # Essence-type items redirect to Jane's chat with the essence activated
    if essence_type == "essence" and essence_folder_name:
        return RedirectResponse(url=f"/?essence={essence_folder_name}", status_code=302)

    if not template_path:
        raise HTTPException(status_code=404, detail=f"No UI template found for essence '{essence_name}'")

    with open(template_path) as f:
        html = f.read()
    return HTMLResponse(html)




# ─── Instant Commands (no LLM, no ChromaDB, <100ms) ─────────────────────────

def _check_instant_command(message: str, platform: str = "web") -> str | None:
    """Check if a message is an exact data-lookup command. Returns formatted result or None.

    Only matches short imperative commands, not questions or sentences that
    happen to contain the keyword.
    """
    import subprocess as _sp
    msg = message.lower().strip().rstrip(":").strip()
    python_bin = sys.executable

    # Only match short commands (under 40 chars) to avoid catching questions
    if len(msg) > 40:
        return None

    _JOB_QUEUE_PHRASES = {
        "show job queue", "job queue", "show me the job queue",
        "show jobs", "list jobs", "pending jobs", "/jobs",
    }
    if msg in _JOB_QUEUE_PHRASES:
        try:
            r = _sp.run([python_bin, os.path.join(CODE_ROOT, "agent_skills", "show_job_queue.py"), "--markdown"],
                        capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.stdout.strip() else "Job queue is empty."
        except Exception:
            return "Could not load job queue."

    _COMPLETED_JOBS_PHRASES = {
        "show completed jobs", "completed jobs", "show me completed jobs",
        "finished jobs", "done jobs", "completed job queue",
    }
    if msg in _COMPLETED_JOBS_PHRASES:
        try:
            r = _sp.run([python_bin, os.path.join(CODE_ROOT, "agent_skills", "show_job_queue.py"), "--completed", "--markdown"],
                        capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.stdout.strip() else "No completed jobs."
        except Exception:
            return "Could not load completed jobs."

    _COMMANDS_PHRASES = {"my commands", "commands", "show commands", "show me my commands", "list commands"}
    if msg in _COMMANDS_PHRASES:
        return (
            "| Command | What it does |\n"
            "|---|---|\n"
            "| `add job:` | Creates a job spec from conversation |\n"
            "| `show job queue:` | Shows jobs table |\n"
            "| `run job queue:` | Executes highest-priority job |\n"
            "| `build essence:` | Starts essence builder interview |\n"
            "| `my commands:` | Shows this reference |"
        )

    if msg in ("show cron jobs", "cron jobs", "cron"):
        try:
            r = _sp.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
            lines = [l for l in r.stdout.strip().split("\n") if l.strip() and not l.startswith("#")]
            if not lines:
                return "No active cron jobs."
            return "```\n" + "\n".join(lines) + "\n```"
        except Exception:
            return "Could not load cron jobs."

    return None


# ─── Chat Stream ─────────────────────────────────────────────────────────────

async def _handle_jane_chat_stream(body: ChatMessage, request: Request):
    # Allow internal requests from localhost (prompt queue runner)
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost"):
        session_id = body.session_id or "prompt_queue_session"
        trusted_device_id = None
    else:
        session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        _logger.warning(
            "Rejected jane stream request: no authenticated session body_session=%s ip=%s",
            _session_log_id(body.session_id),
            _client_ip(request),
        )
        raise HTTPException(status_code=401, detail="Not authenticated")
    _logger.info(
        "Accepted jane stream request session=%s msg_len=%d file_ctx=%s body_session=%s ip=%s",
        _session_log_id(session_id),
        len(body.message or ""),
        bool(body.file_context),
        _session_log_id(body.session_id),
        _client_ip(request),
    )

    # ── Instant commands: bypass all LLM processing for pure data lookups ──
    raw_message = (body.message or "").strip()
    instant_result = _check_instant_command(raw_message, platform=body.platform or "web")
    if instant_result is not None:
        async def _instant_stream():
            yield json.dumps({"type": "delta", "data": instant_result}) + "\n"
            yield json.dumps({"type": "done", "data": instant_result}) + "\n"
        return StreamingResponse(_instant_stream(), media_type="application/x-ndjson")

    # ── Big-task offload check ──────────────────────────────────────────────
    from jane_web.task_classifier import classify_task, strip_bg_prefix
    from jane_web.task_offloader import offload_task

    task_class = classify_task(raw_message)

    if task_class == "big":
        clean_message = strip_bg_prefix(raw_message)
        task_id = offload_task(clean_message, session_id, body.file_context, body.platform)
        _logger.info(
            "Offloaded big task %s session=%s msg_len=%d",
            task_id, _session_log_id(session_id), len(clean_message),
        )

        async def offloaded_stream():
            yield json.dumps({
                "type": "offloaded",
                "data": "I'll work on that in the background. You'll see progress updates here as I go.",
                "task_id": task_id,
            }) + "\n"
            yield json.dumps({"type": "done", "data": "I'll work on that in the background. You'll see progress updates here as I go."}) + "\n"

        response = StreamingResponse(
            offloaded_stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response

    # ── Normal streaming flow ─────────────────────────────────────────────
    async def event_stream():
        user_id = get_session_user(session_id) or _default_user_id()
        _logger.info(
            "Starting jane stream generator session=%s user=%s",
            _session_log_id(session_id),
            user_id,
        )
        try:
            async with asyncio.timeout(1800):  # 30 minute timeout (matches Claude idle timeout)
                async for chunk in stream_message(user_id, session_id, body.message, body.file_context, platform=body.platform, tts_enabled=body.tts_enabled or False):
                    yield chunk
        except (ConnectionError, OSError) as exc:
            _logger.warning(
                "jane_chat_stream connection error session=%s user=%s: %s",
                _session_log_id(session_id), user_id, exc,
            )
            yield json.dumps({"type": "error", "data": "⚠️ Connection lost. Please try again."}) + "\n"
        except Exception as exc:
            _logger.exception(
                "jane_chat_stream failed active_session=%s body_session=%s user=%s: %s",
                _session_log_id(session_id),
                _session_log_id(body.session_id),
                user_id,
                exc,
            )
            yield json.dumps({"type": "error", "data": f"⚠️ Could not reach Jane: {exc}"}) + "\n"
            return
        finally:
            _logger.info("Jane stream generator closed session=%s", _session_log_id(session_id))

    response = StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
    if get_session_id(request) != session_id:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
        response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                            max_age=60 * 60 * 24 * 30)
    return response


# ─── Permission Gate (web-based tool approval) ──────────────────────────────

@app.post("/api/jane/permission/request")
async def permission_request_endpoint(request: Request):
    """Called by the PreToolUse hook inside the CLI. Blocks until user responds."""
    from jane_web.permission_broker import get_permission_broker
    body = await request.json()
    broker = get_permission_broker()
    req = await broker.create_request(
        request_id=body["request_id"],
        tool_name=body["tool_name"],
        tool_input=body.get("tool_input", {}),
        session_id=body.get("session_id", ""),
    )
    approved = await broker.wait_for_response(req)
    return JSONResponse({"approved": approved, "reason": req.reason})


@app.post("/api/jane/permission/respond")
async def permission_respond_endpoint(request: Request):
    """Called by the web frontend when user clicks approve/deny."""
    from jane_web.permission_broker import get_permission_broker
    body = await request.json()
    broker = get_permission_broker()
    success = broker.resolve(
        request_id=body["request_id"],
        approved=body.get("approved", False),
        reason=body.get("reason", ""),
    )
    return JSONResponse({"ok": success})


@app.get("/api/jane/permission/pending")
async def permission_pending_endpoint(request: Request):
    """Return all pending permission requests (for page reload recovery)."""
    from jane_web.permission_broker import get_permission_broker
    broker = get_permission_broker()
    pending = broker.get_all_pending()
    return JSONResponse({"requests": [
        {
            "request_id": r.request_id,
            "tool_name": r.tool_name,
            "tool_input": r.tool_input,
            "created_at": r.created_at,
        }
        for r in pending
    ]})


@app.post("/api/jane/chat/stream")
async def jane_chat_stream(body: ChatMessage, request: Request):
    return await _handle_jane_chat_stream(body, request)


@app.post("/api/jane/init-session")
async def jane_init_session(body: SessionControl, request: Request):
    """Pre-warm Jane's Claude CLI session so the first real message is fast.

    Triggers the full session init (CLAUDE.md, hooks, context build) with a
    lightweight prompt. Returns a streaming NDJSON response with status events
    and a greeting.
    """
    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from jane_proxy import _get_brain_name, _use_persistent_claude, _use_persistent_codex, _get_execution_profile
    except ImportError:
        from .jane_proxy import _get_brain_name, _use_persistent_claude, _use_persistent_codex, _get_execution_profile
    from jane.context_builder import build_jane_context_async

    brain_name = _get_brain_name()
    if not (_use_persistent_claude(brain_name) or _use_persistent_codex(brain_name)):
        # Non-persistent brains don't need pre-warming
        return JSONResponse({"status": "skipped", "greeting": "Hey! What's on your mind?"})

    if _use_persistent_claude(brain_name):
        from jane.persistent_claude import get_claude_persistent_manager
        manager = get_claude_persistent_manager()
        init_status = "Sending init prompt to Claude..."
    else:
        from jane.persistent_codex import get_codex_persistent_manager
        manager = get_codex_persistent_manager()
        init_status = "Sending init prompt to Codex..."
    session = await manager.get(body.session_id or session_id)

    if not session.is_fresh():
        # Already warm — no init needed
        return JSONResponse({"status": "already_warm", "greeting": ""})

    # Build context for the init turn, streaming status updates
    user_id = get_session_user(session_id) or _default_user_id()

    async def _stream_init():
        status_queue: asyncio.Queue = asyncio.Queue()

        def _emit_status(msg: str):
            status_queue.put_nowait(msg)

        try:
            # Build context with status callbacks
            _emit_status("Loading personality and context...")
            ctx = await build_jane_context_async(
                "Session initialization",
                [],
                session_id=body.session_id or session_id,
                platform="web",
                on_status=_emit_status,
            )

            # Drain and yield all queued status events
            while not status_queue.empty():
                s = status_queue.get_nowait()
                yield json.dumps({"type": "status", "data": s}) + "\n"

            yield json.dumps({"type": "status", "data": init_status}) + "\n"

            init_prompt = (
                f"{ctx.system_prompt}\n\n"
                "This is a session initialization. Read your configuration and prepare for conversation. "
                "Respond with a single short, warm greeting (1 sentence max). Do not ask questions."
            )

            profile = _get_execution_profile(brain_name)
            greeting = await manager.run_turn(
                body.session_id or session_id,
                init_prompt,
                on_delta=lambda d: None,
                on_status=lambda s: None,
                timeout_seconds=profile.timeout_seconds,
                model=None,
                yolo=profile.mode == "yolo",
            )
            yield json.dumps({"type": "done", "data": greeting.strip()}) + "\n"
        except Exception as e:
            _logger.exception("Init session failed")
            yield json.dumps({"type": "done", "data": "Hey! Ready when you are."}) + "\n"

    return StreamingResponse(_stream_init(), media_type="application/x-ndjson")


# ─── Essence Management API ──────────────────────────────────────────────────

from agent_skills.essence_loader import (
    load_essence,
    unload_essence,
    delete_essence,
    list_available_essences,
    list_available,
    list_loaded_essences,
    EssenceState,
)

_essence_states: dict[str, EssenceState] = {}
_capability_registry = None  # Initialized in _auto_load_essences()
_ACTIVE_ESSENCE_PATH = os.path.join(VESSENCE_DATA_HOME, "data", "active_essence.json")


def _read_active_essences() -> list[str]:
    """Read the active essence list from disk."""
    try:
        with open(_ACTIVE_ESSENCE_PATH) as f:
            data = json.load(f)
        return data.get("active", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _write_active_essences(active: list[str]) -> None:
    """Write the active essence list to disk."""
    os.makedirs(os.path.dirname(_ACTIVE_ESSENCE_PATH), exist_ok=True)
    with open(_ACTIVE_ESSENCE_PATH, "w") as f:
        json.dump({"active": active}, f, indent=2)


@app.get("/api/essences")
async def list_essences(type: str = "all", _=Depends(require_auth)):
    """List all available essences/tools. Optional ?type=tool or ?type=essence filter."""
    available = list_available_essences(type_filter=type)
    loaded_names = list_loaded_essences()
    results = []
    for e in available:
        manifest_path = os.path.join(e["path"], "manifest.json")
        capabilities = {}
        preferred_model = {}
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            capabilities = manifest.get("capabilities", {})
            preferred_model = manifest.get("preferred_model", {})
        except (json.JSONDecodeError, OSError):
            pass
        results.append({
            "name": e["name"],
            "role_title": e.get("role_title", ""),
            "description": e.get("description", ""),
            "type": e.get("type", "tool"),
            "has_brain": e.get("has_brain", False),
            "loaded": e["name"] in loaded_names,
            "capabilities": capabilities,
            "preferred_model": preferred_model,
        })
    return results


@app.get("/api/essences/active")
async def get_active_essences(_=Depends(require_auth)):
    """Get the currently active essence(s)."""
    return {"active": _read_active_essences()}


@app.get("/api/essences/work_log/activities")
async def get_work_log_activities_route(count: int = 50, _=Depends(require_auth)):
    """Get recent activities from the Work Log essence."""
    try:
        from agent_skills.work_log_tools import get_recent_activities
        activities = get_recent_activities(count=count)
        return {"activities": activities}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Work Log error: {exc}")


@app.get("/api/essences/capabilities")
async def get_capabilities_map_route(_=Depends(require_auth)):
    """Get the capability -> essence mapping for all loaded essences."""
    if _capability_registry is None:
        return {"capabilities": {}}
    return {"capabilities": _capability_registry._providers}


@app.get("/api/essences/{essence_name}")
async def get_essence_detail(essence_name: str, _=Depends(require_auth)):
    """Get details of a specific essence."""
    available = list_available_essences()
    match = None
    for e in available:
        if e["name"] == essence_name:
            match = e
            break
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    manifest_path = os.path.join(match["path"], "manifest.json")
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read manifest: {exc}")
    loaded_names = list_loaded_essences()
    manifest["loaded"] = essence_name in loaded_names
    return manifest


@app.post("/api/essences/{essence_name}/load")
async def load_essence_endpoint(essence_name: str, _=Depends(require_auth)):
    """Load an essence by name."""
    available = list_available_essences()
    match = None
    for e in available:
        if e["name"] == essence_name:
            match = e
            break
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    try:
        state = load_essence(match["path"])
        _essence_states[essence_name] = state
        # Register capabilities
        if _capability_registry:
            caps = state.capabilities.get("provides", [])
            if caps:
                _capability_registry.register(essence_name, caps)
        return {
            "status": "loaded",
            "role_title": state.role_title,
            "permissions": state.manifest.get("permissions", []),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/essences/{essence_name}/unload")
async def unload_essence_endpoint(essence_name: str, _=Depends(require_auth)):
    """Unload a loaded essence."""
    try:
        unload_essence(essence_name)
        _essence_states.pop(essence_name, None)
        # Unregister capabilities
        if _capability_registry:
            _capability_registry.unregister(essence_name)
        active = _read_active_essences()
        if essence_name in active:
            active.remove(essence_name)
            _write_active_essences(active)
        return {"status": "unloaded"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' is not loaded")


@app.delete("/api/essences/{essence_name}")
async def delete_essence_endpoint(essence_name: str, port_memory: bool = False, _=Depends(require_auth)):
    """Delete an essence. Use ?port_memory=true to port memory to Jane first."""
    try:
        delete_essence(essence_name, port_memory=port_memory)
        _essence_states.pop(essence_name, None)
        active = _read_active_essences()
        if essence_name in active:
            active.remove(essence_name)
            _write_active_essences(active)
        return {"status": "deleted", "memory_ported": port_memory}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/essences/{essence_name}/activate")
async def activate_essence(essence_name: str, _=Depends(require_auth)):
    """Set an essence as the active one. Accepts display name or folder name."""
    available = list_available_essences()
    # First try exact match by display name
    match = next((e for e in available if e["name"] == essence_name), None)
    # If not found, try matching by folder name (e.g. "tax_accountant_2025")
    if not match:
        match = next(
            (e for e in available if os.path.basename(e["path"]) == essence_name),
            None,
        )
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    _write_active_essences([match["name"]])
    # Invalidate context builder cache so Jane picks up the new essence immediately
    _invalidate_essence_context_cache()
    return {"status": "activated", "name": match["name"]}


@app.post("/api/essences/deactivate")
async def deactivate_essence(_=Depends(require_auth)):
    """Deactivate all active essences — return Jane to baseline."""
    _write_active_essences([])
    _invalidate_essence_context_cache()
    return {"status": "deactivated"}


@app.post("/api/jane/invalidate-essence-cache")
async def invalidate_essence_cache(_=Depends(require_auth)):
    """Invalidate the context builder's cached essence personality and tools."""
    _invalidate_essence_context_cache()
    return {"status": "ok"}


def _invalidate_essence_context_cache():
    """Clear essence-related entries from the context builder's in-memory cache."""
    try:
        from jane.context_builder import _context_cache
        for key in ["essence_personality", "essence_tools"]:
            _context_cache.pop(key, None)
    except Exception:
        pass  # non-fatal — cache will expire naturally within 5 minutes


# ─── Work Log Activity Logging ────────────────────────────────────────────────

def _log_work_activity(description: str, category: str = "general") -> None:
    """Log an activity to the Work Log essence if it is loaded."""
    try:
        from agent_skills.work_log_tools import log_activity
        log_activity(description, category=category)
    except Exception:
        pass  # Work log not available — non-fatal


# ─── Daily Briefing API ──────────────────────────────────────────────────────

_BRIEFING_FUNCTIONS_DIR = os.path.join(
    os.environ.get("TOOLS_DIR",
                   os.path.join(os.path.expanduser("~"), "ambient", "tools")),
    "daily_briefing", "functions"
)


def _briefing_tools():
    """Lazy import of daily briefing custom_tools."""
    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
    import custom_tools as _bt
    return _bt


@app.get("/api/briefing/articles")
async def get_briefing_articles(topic: Optional[str] = None, category: Optional[str] = None, _=Depends(require_auth)):
    """Get latest briefing articles. Filter by topic name or category."""
    bt = _briefing_tools()
    result = bt.get_briefing_cards()
    if result.get("status") != "ok":
        return result
    cards = result["cards"]
    if category and category != "All":
        cards = [c for c in cards if category in c.get("categories", [])]
    elif topic:
        cards = [c for c in cards if c.get("topic", "").lower() == topic.lower()]
    return {"status": "ok", "cards": cards, "card_count": len(cards), "categories": result.get("categories", [])}


@app.get("/api/briefing/article/{article_id}")
async def get_briefing_article_detail(article_id: str, _=Depends(require_auth)):
    """Get full article detail with comprehensive summary."""
    bt = _briefing_tools()
    result = bt.get_article_detail(article_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
    return result


@app.get("/api/briefing/audio/{article_id}/{summary_type}")
async def briefing_audio(article_id: str, summary_type: str = "brief", _=Depends(require_auth)):
    """Serve pre-generated TTS audio for a briefing article (Opus/OGG preferred, WAV fallback)."""
    audio_dir = os.path.join(
        os.environ.get("TOOLS_DIR",
                       os.path.join(os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient")), "tools")),
        "daily_briefing", "essence_data", "audio"
    )
    # Prefer Opus/OGG, fall back to legacy WAV
    ogg_path = os.path.join(audio_dir, f"{article_id}_{summary_type}.ogg")
    wav_path = os.path.join(audio_dir, f"{article_id}_{summary_type}.wav")
    if os.path.isfile(ogg_path):
        return FileResponse(ogg_path, media_type="audio/ogg")
    if os.path.isfile(wav_path):
        return FileResponse(wav_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio not available for this article")


@app.get("/api/briefing/topics")
async def get_briefing_topics(_=Depends(require_auth)):
    """Get all tracked topics."""
    bt = _briefing_tools()
    return bt.list_topics()


@app.post("/api/briefing/topics")
async def add_briefing_topic(body: dict, _=Depends(require_auth)):
    """Add a topic. Body: {name, keywords, priority}"""
    bt = _briefing_tools()
    name = body.get("name", "")
    keywords = body.get("keywords", [])
    priority = body.get("priority", "normal")
    if not name or not keywords:
        raise HTTPException(status_code=422, detail="name and keywords are required")
    category = body.get("category", "General")
    return bt.add_topic(name, keywords, priority, category)


@app.delete("/api/briefing/topics/{topic_name}")
async def delete_briefing_topic(topic_name: str, _=Depends(require_auth)):
    """Remove a topic."""
    bt = _briefing_tools()
    result = bt.remove_topic(topic_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
    return result


# ── Background shared-article processor ──────────────────────────────────────
_shared_queue_processor_task: Optional[asyncio.Task] = None


async def _resume_shared_queue_if_needed():
    """On startup, check if there are unprocessed shared articles and resume processing."""
    global _shared_queue_processor_task
    await asyncio.sleep(30)  # let the server finish warming up first
    try:
        queue_file = os.path.join(os.path.dirname(_BRIEFING_FUNCTIONS_DIR), "working_files", "shared_queue.json")
        if not os.path.exists(queue_file):
            return
        with open(queue_file, "r") as f:
            queue = json.load(f)
        unprocessed = [e for e in queue if not e.get("processed")]
        if not unprocessed:
            return
        _logger.info("Found %d unprocessed shared articles on startup — resuming queue processor", len(unprocessed))
        if _shared_queue_processor_task is None or _shared_queue_processor_task.done():
            _shared_queue_processor_task = asyncio.create_task(_process_shared_queue_draining())
            _background_tasks.add(_shared_queue_processor_task)
            _shared_queue_processor_task.add_done_callback(_background_tasks.discard)
    except Exception:
        _logger.exception("Failed to check shared queue on startup")
_RESOURCE_POLL_INTERVAL = 30    # seconds between resource re-checks when busy
_RESOURCE_MAX_WAIT = 3600       # give up after 1 hour total


def _check_resources_available() -> bool:
    """Check if system load is below 60% across CPU, GPU, RAM, VRAM."""
    try:
        _skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_skills")
        if _skills_dir not in sys.path:
            sys.path.insert(0, _skills_dir)
        from system_load import has_ample_resources
        return has_ample_resources(threshold_pct=60)
    except Exception:
        return True  # if check fails, proceed


async def _process_shared_queue_draining():
    """Process queued articles one at a time, checking resources before each.

    Starts immediately on article submission. Between each article, re-checks
    that system load is below 60%. If busy, polls every 30s until resources
    free up (up to 1 hour total wait).
    """
    loop = asyncio.get_running_loop()
    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
    import run_briefing as _rb

    total_processed = 0
    waited_total = 0

    while True:
        # Wait for resources before processing the next article
        while not _check_resources_available():
            if waited_total >= _RESOURCE_MAX_WAIT:
                _logger.info("Resources busy for %ds — sleeping 10min before retrying (%d processed so far)",
                             waited_total, total_processed)
                await asyncio.sleep(600)  # sleep 10 minutes then reset wait timer
                waited_total = 0
                continue
            _logger.debug("System busy (>60%%) — rechecking in %ds (waited %ds total)",
                          _RESOURCE_POLL_INTERVAL, waited_total)
            await asyncio.sleep(_RESOURCE_POLL_INTERVAL)
            waited_total += _RESOURCE_POLL_INTERVAL

        # Process exactly one article
        try:
            result = await loop.run_in_executor(None, _rb.process_one_queued_article)
        except Exception:
            _logger.exception("Error processing queued article")
            return

        if not result.get("processed"):
            # Queue is empty
            if total_processed:
                _logger.info("Queue drained — %d article(s) processed", total_processed)
            return

        total_processed += 1
        waited_total = 0  # reset wait timer after successful processing
        remaining = result.get("remaining", 0)
        _logger.info("Processed article %s — %d remaining in queue",
                      result.get("article_id", "?"), remaining)

        if remaining == 0:
            _logger.info("Queue drained — %d article(s) processed", total_processed)
            return


@app.post("/api/briefing/articles/submit")
async def submit_briefing_article(request: Request, _=Depends(require_auth)):
    """Accept a shared article URL and queue it for processing."""
    global _shared_queue_processor_task
    body = await request.json()
    url = body.get("url", "").strip()
    if not url or not re.match(r'^https?://', url):
        raise HTTPException(status_code=400, detail="A valid URL starting with http(s):// is required")
    bt = _briefing_tools()
    result = bt.submit_article(url)

    # Spawn background processor if none is already running
    if _shared_queue_processor_task is None or _shared_queue_processor_task.done():
        _shared_queue_processor_task = asyncio.create_task(_process_shared_queue_draining())
        _background_tasks.add(_shared_queue_processor_task)
        _shared_queue_processor_task.add_done_callback(_background_tasks.discard)
        _logger.info("Spawned background shared-queue processor for URL: %s", url)
    else:
        _logger.info("Background shared-queue processor already running — skipping spawn for URL: %s", url)

    return result


@app.post("/api/briefing/fetch")
async def trigger_briefing_fetch(_=Depends(require_auth)):
    """Manually trigger a briefing fetch."""
    bt = _briefing_tools()
    result = bt.fetch_and_summarize_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Fetch failed"))
    return result


@app.post("/api/briefing/article/{article_id}/dismiss")
async def dismiss_briefing_article(article_id: str, _=Depends(require_auth)):
    """Mark an article as dismissed ('heard it')."""
    bt = _briefing_tools()
    return bt.dismiss_article(article_id)


@app.delete("/api/briefing/article/{article_id}/dismiss")
async def undismiss_briefing_article(article_id: str, _=Depends(require_auth)):
    """Un-dismiss an article."""
    bt = _briefing_tools()
    return bt.undismiss_article(article_id)


_SAVED_ARTICLES_DIR = Path(os.path.expanduser("~/ambient/vessence-data/briefing_saved"))
_VAULT_SAVED_ARTICLES = Path(os.path.expanduser("~/ambient/vault/saved_articles"))


@app.post("/api/briefing/saved")
async def save_briefing_article(request: Request, _=Depends(require_auth)):
    """Save an article permanently to a category. Saved articles are never auto-deleted."""
    body = await request.json()
    article_id = body.get("article_id")
    category = body.get("category", "Uncategorized")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id required")

    _SAVED_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    saved_file = _SAVED_ARTICLES_DIR / "saved.json"

    saved = {}
    if saved_file.exists():
        async with aiofiles.open(saved_file, "r") as f:
            saved = json.loads(await f.read())

    # Find article data from current briefing articles cache
    article_data = None
    articles_dir = Path(os.environ.get("TOOLS_DIR",
                        os.path.join(os.path.expanduser("~"), "ambient", "tools"))) / "daily_briefing" / "essence_data" / "articles"
    article_file = articles_dir / f"{article_id}.json"
    if article_file.exists():
        async with aiofiles.open(article_file, "r") as f:
            article_data = json.loads(await f.read())

    # Store: keyed by article_id, includes category and saved timestamp
    saved[article_id] = {
        "article_id": article_id,
        "category": category,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "article": article_data,
    }

    async with aiofiles.open(saved_file, "w") as f:
        await f.write(json.dumps(saved, indent=2))

    # Also save to vault as file: vault/saved_articles/<group>/<article_id>.json
    vault_group_dir = _VAULT_SAVED_ARTICLES / category
    vault_group_dir.mkdir(parents=True, exist_ok=True)
    vault_article_file = vault_group_dir / f"{article_id}.json"
    async with aiofiles.open(vault_article_file, "w") as f:
        await f.write(json.dumps(saved[article_id], indent=2))
    _logger.info("Saved article %s to vault group '%s'", article_id, category)

    return {"status": "ok", "article_id": article_id, "category": category}


@app.get("/api/briefing/saved/categories")
async def list_saved_categories(_=Depends(require_auth)):
    """List all categories that have saved articles (from vault folders)."""
    cats = set()
    # Scan vault folders — these are the source of truth for group names
    if _VAULT_SAVED_ARTICLES.exists():
        for d in _VAULT_SAVED_ARTICLES.iterdir():
            if d.is_dir() and any(d.glob("*.json")):
                cats.add(d.name)
    # Also check JSON index for anything not yet in vault
    saved_file = _SAVED_ARTICLES_DIR / "saved.json"
    if saved_file.exists():
        async with aiofiles.open(saved_file, "r") as f:
            saved = json.loads(await f.read())
        cats.update(v.get("category", "Uncategorized") for v in saved.values())
    return {"categories": sorted(cats)}


@app.get("/api/briefing/saved")
async def list_saved_articles(category: str = None, _=Depends(require_auth)):
    """List saved articles, optionally filtered by category."""
    saved_file = _SAVED_ARTICLES_DIR / "saved.json"
    if not saved_file.exists():
        return {"articles": []}
    async with aiofiles.open(saved_file, "r") as f:
        saved = json.loads(await f.read())
    items = list(saved.values())
    if category:
        items = [i for i in items if i.get("category") == category]
    items.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return {"articles": items}


@app.delete("/api/briefing/saved/{article_id}")
async def unsave_briefing_article(article_id: str, _=Depends(require_auth)):
    """Remove an article from saved collection."""
    saved_file = _SAVED_ARTICLES_DIR / "saved.json"
    if not saved_file.exists():
        raise HTTPException(status_code=404, detail="No saved articles")
    async with aiofiles.open(saved_file, "r") as f:
        saved = json.loads(await f.read())
    if article_id not in saved:
        raise HTTPException(status_code=404, detail="Article not saved")
    category = saved[article_id].get("category", "")
    del saved[article_id]
    async with aiofiles.open(saved_file, "w") as f:
        await f.write(json.dumps(saved, indent=2))
    # Remove from vault too
    if category:
        vault_file = _VAULT_SAVED_ARTICLES / category / f"{article_id}.json"
        if vault_file.exists():
            vault_file.unlink()
            # Remove empty group folder
            vault_group = vault_file.parent
            if vault_group.exists() and not any(vault_group.iterdir()):
                vault_group.rmdir()
    return {"status": "ok", "article_id": article_id}


@app.get("/api/briefing/search")
async def search_briefing_articles(q: str, _=Depends(require_auth)):
    """Search past articles via ChromaDB."""
    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
    from article_indexer import search_articles
    results = search_articles(q, n_results=10)
    return {"status": "ok", "results": results, "count": len(results)}


@app.get("/api/briefing/image/{article_id}")
async def get_briefing_image(article_id: str):
    """Serve a cached article image."""
    images_dir = Path(os.environ.get("TOOLS_DIR",
                      os.path.join(os.path.expanduser("~"), "ambient", "tools"))) / "daily_briefing" / "essence_data" / "images"
    # Try common extensions
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        img_path = images_dir / f"{article_id}{ext}"
        if img_path.exists():
            return FileResponse(str(img_path))
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/briefing/archive")
async def list_briefing_archive(_=Depends(require_auth)):
    """List available archived briefing dates."""
    archive_dir = Path(os.path.expanduser("~/ambient/vessence-data/briefings"))
    if not archive_dir.exists():
        return {"status": "ok", "dates": []}
    files = sorted(archive_dir.glob("*.json"), key=lambda f: f.name, reverse=True)
    dates = [f.stem for f in files]
    return {"status": "ok", "dates": dates}


@app.get("/api/briefing/archive/{date}")
async def get_archived_briefing(date: str, _=Depends(require_auth)):
    """Get a specific archived briefing by date."""
    archive_dir = Path(os.path.expanduser("~/ambient/vessence-data/briefings"))
    file_path = archive_dir / f"{date}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archive not found")

    async with aiofiles.open(file_path, "r") as f:
        data = json.loads(await f.read())
    return data


# ─── Tax Accountant 2025 Routes ──────────────────────────────────────────────

_TAX_ESSENCE_DIR = os.path.join(os.path.expanduser("~/ambient/essences"), "tax_accountant_2025")
_TAX_FUNCTIONS_DIR = os.path.join(_TAX_ESSENCE_DIR, "functions")

def _run_tax_tool(tool_name: str, args: dict = None) -> dict:
    """Run a tax accountant tool and return the result."""
    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    tools_path = os.path.join(_TAX_FUNCTIONS_DIR, "custom_tools.py")
    cmd = [python_bin, tools_path, tool_name]
    if args:
        cmd.append(json.dumps(args))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                            cwd=_TAX_FUNCTIONS_DIR)
    if result.returncode != 0:
        return {"status": "error", "message": result.stderr[:500]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "ok", "output": result.stdout.strip()}


@app.get("/tax-accountant")
async def tax_accountant_page(request: Request, _=Depends(require_auth)):
    """Redirect to Jane's chat with the tax accountant essence activated."""
    return RedirectResponse(url="/?essence=tax_accountant_2025", status_code=302)


@app.post("/api/tax/interview/start")
async def tax_interview_start(_=Depends(require_auth)):
    """Start or restart the tax interview."""
    return JSONResponse(_run_tax_tool("interview_step", {"step_id": "filing_status"}))


@app.post("/api/tax/interview/answer")
async def tax_interview_answer(request: Request, _=Depends(require_auth)):
    """Submit an answer to the current interview step."""
    body = await request.json()
    step_id = body.get("step_id", "filing_status")
    user_response = body.get("response", {})
    return JSONResponse(_run_tax_tool("interview_step", {
        "step_id": step_id,
        "user_response": user_response
    }))


@app.get("/api/tax/interview/state")
async def tax_interview_state(_=Depends(require_auth)):
    """Get the current interview state."""
    return JSONResponse(_run_tax_tool("get_interview_state"))


@app.post("/api/tax/calculate")
async def tax_calculate(_=Depends(require_auth)):
    """Run the full tax calculation."""
    return JSONResponse(_run_tax_tool("calculate_tax"))


@app.get("/api/tax/forms/{form_name}")
async def tax_get_form(form_name: str, _=Depends(require_auth)):
    """Get a generated tax form."""
    output_dir = os.path.join(_TAX_ESSENCE_DIR, "working_files", "output")
    # Find the most recent file matching form_name
    if os.path.isdir(output_dir):
        matches = sorted([f for f in os.listdir(output_dir) if f.startswith(form_name)], reverse=True)
        if matches:
            file_path = os.path.join(output_dir, matches[0])
            return FileResponse(file_path, filename=matches[0])
    raise HTTPException(status_code=404, detail=f"Form '{form_name}' not found")


@app.get("/api/tax/summary")
async def tax_summary(_=Depends(require_auth)):
    """Get the most recent tax calculation summary."""
    result_path = os.path.join(_TAX_ESSENCE_DIR, "working_files", "calculations", "tax_result.json")
    if not os.path.exists(result_path):
        return JSONResponse({"status": "error", "message": "No calculation found. Run calculate first."})
    with open(result_path) as f:
        return JSONResponse(json.load(f))


@app.post("/api/tax/upload")
async def tax_upload_document(file: UploadFile = File(...), doc_type: str = Form(""), _=Depends(require_auth)):
    """Upload a tax document for processing."""
    uploads_dir = os.path.join(_TAX_ESSENCE_DIR, "user_data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return JSONResponse(_run_tax_tool("upload_document", {
        "file_path": file_path,
        "doc_type": doc_type
    }))


@app.post("/api/tax/reset")
async def tax_reset(_=Depends(require_auth)):
    """Reset the tax interview."""
    return JSONResponse(_run_tax_tool("reset_interview"))


@app.get("/api/tax/checklist")
async def tax_checklist(_=Depends(require_auth)):
    """Get the document checklist."""
    return JSONResponse(_run_tax_tool("get_document_checklist"))


@app.post("/api/tax/generate")
async def tax_generate_forms(_=Depends(require_auth)):
    """Generate all tax forms."""
    return JSONResponse(_run_tax_tool("generate_forms"))


@app.get("/api/tax/knowledge/search")
async def tax_knowledge_search(q: str = "", _=Depends(require_auth)):
    """Search the tax knowledge base."""
    if not q:
        return JSONResponse({"status": "error", "message": "Query parameter 'q' required"})
    try:
        chroma_path = os.path.join(_TAX_ESSENCE_DIR, "knowledge", "chromadb")
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        coll = chroma_client.get_collection("tax_knowledge_2025")
        results = coll.query(query_texts=[q], n_results=5)
        return JSONResponse({
            "status": "ok",
            "results": [
                {
                    "content": doc,
                    "metadata": meta,
                    "distance": dist
                }
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )
            ]
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


# ── CLI Login (runs inside Jane container where CLI is installed) ─────────────

import select as _select

_cli_login_process = None
_cli_login_authenticated = False
_cli_login_transcript_path: str | None = None
_cli_login_provider: str | None = None
_cli_login_local_port: int | None = None
_cli_login_oauth_state: str | None = None
_cli_login_pty_master_fd: int | None = None
# Self-managed OAuth (bypasses CLI's broken Docker auth)
_claude_oauth_verifier: str | None = None
_claude_oauth_state: str | None = None
_gemini_oauth_verifier: str | None = None
_gemini_oauth_state: str | None = None

_auth_status_cache: dict[str, tuple[float, dict]] = {}


_claude_refresh_last_failure: float = 0.0  # timestamp of last failed refresh
_CLAUDE_REFRESH_COOLDOWN = 300  # seconds (5 minutes) before retrying after failure


def _attempt_claude_token_refresh() -> bool:
    """Attempt to refresh the Claude OAuth token using the refresh token. Sync version."""
    global _claude_refresh_last_failure

    # Cooldown: don't retry if we failed recently
    if _claude_refresh_last_failure and (time.time() - _claude_refresh_last_failure) < _CLAUDE_REFRESH_COOLDOWN:
        return False

    creds_path = Path.home() / ".claude" / ".credentials.json"
    if not creds_path.exists():
        return False

    try:
        creds = json.loads(creds_path.read_text())
        refresh_token = creds.get("claudeAiOauth", {}).get("refreshToken")
        if not refresh_token:
            return False

        # Token exchange with backoff
        from urllib.parse import urlencode as _urlencode
        import urllib.request as _urllib_req
        token_data = _urlencode({
            "grant_type": "refresh_token",
            "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
            "refresh_token": refresh_token,
        }).encode()

        for attempt in range(3):
            try:
                token_req = _urllib_req.Request(
                    "https://platform.claude.com/v1/oauth/token",
                    data=token_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "claude-code/2.1.86",
                        "Accept": "application/json",
                    },
                )
                token_resp = _urllib_req.urlopen(token_req, timeout=15)
                tokens = json.loads(token_resp.read())

                # Update credentials
                scopes = tokens.get("scope", "").split(" ") if tokens.get("scope") else creds["claudeAiOauth"].get("scopes", [])
                creds["claudeAiOauth"].update({
                    "accessToken": tokens["access_token"],
                    "refreshToken": tokens.get("refresh_token", refresh_token),
                    "expiresAt": int(time.time() * 1000) + tokens.get("expires_in", 3600) * 1000,
                    "scopes": scopes,
                })
                creds_path.write_text(json.dumps(creds), encoding="utf-8")
                return True
            except Exception as exc:
                if hasattr(exc, "code") and exc.code == 429:
                    # Exponential backoff
                    wait_time = 2 ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                break
    except Exception:
        pass

    _claude_refresh_last_failure = time.time()
    return False


def _cli_login_candidates(provider: str) -> list[list[str]]:
    provider = (provider or "").lower()
    if provider == "claude":
        # Claude: self-managed OAuth (bypass CLI, handled in /api/cli-login)
        return [["claude", "auth", "login"]]
    if provider == "gemini":
        return [["gemini", "auth", "login"]]
    if provider == "openai":
        # Codex: device-auth flow works in Docker (no localhost callback needed)
        return [["codex", "login", "--device-auth"]]
    return []


def _cli_binary_for_provider(provider: str) -> str | None:
    candidates = _cli_login_candidates(provider)
    return candidates[0][0] if candidates else None


def _mask_email(value: str) -> str:
    if "@" not in value:
        return value[:3] + "..." if value else ""
    local, domain = value.split("@", 1)
    local_masked = (local[:2] + "***") if local else "***"
    return f"{local_masked}@{domain}"


def _provider_auth_status_details(provider: str) -> dict:
    provider = (provider or "").lower()
    now = time.time()
    if provider in _auth_status_cache:
        ts, details = _auth_status_cache[provider]
        if now - ts < 5:  # 5 second cache
            return details

    status_cmds = {
        "claude": ["claude", "auth", "status"],
    }
    cmd = status_cmds.get(provider)
    if not cmd:
        return {"provider": provider, "supported": False, "logged_in": False}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return {
            "provider": provider,
            "supported": True,
            "logged_in": False,
            "status_error": str(exc),
        }
    details = {
        "provider": provider,
        "supported": True,
        "status_returncode": result.returncode,
        "logged_in": False,
    }
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            details["status_stderr_tail"] = stderr.splitlines()[-1][:200]
        # No cache for failed status check
        return details
    output = (result.stdout or "").strip()
    if not output:
        # No cache for empty output
        return details

    def parse_output(out_str: str) -> bool:
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict):
                details["logged_in"] = bool(parsed.get("loggedIn"))
                if parsed.get("authMethod"):
                    details["auth_method"] = parsed.get("authMethod")
                if parsed.get("email"):
                    details["email_hint"] = _mask_email(str(parsed.get("email")))
                if parsed.get("subscriptionType"):
                    details["subscription_type"] = parsed.get("subscriptionType")
                return True
        except Exception:
            pass
        lowered = out_str.lower()
        details["logged_in"] = "logged in" in lowered and "not logged in" not in lowered
        details["status_stdout_tail"] = out_str.splitlines()[-1][:200]
        return True

    parse_output(output)

    # Automatic refresh for Claude if not logged in
    if not details.get("logged_in") and provider == "claude":
        if _attempt_claude_token_refresh():
            # Refresh succeeded, re-run status check once (bypass cache)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    output = (result.stdout or "").strip()
                    parse_output(output)
            except Exception:
                pass

    _auth_status_cache[provider] = (now, details)
    return details


def _provider_auth_status(provider: str) -> bool:
    return bool(_provider_auth_status_details(provider).get("logged_in"))


def _cli_login_debug_snapshot(provider: str) -> dict:
    process_state = "missing"
    returncode = None
    if _cli_login_process is not None:
        polled = _cli_login_process.poll()
        process_state = "running" if polled is None else "exited"
        returncode = _cli_login_process.returncode

    transcript_lines = _read_cli_transcript_lines(_cli_login_transcript_path)
    return {
        "provider": provider,
        "process_state": process_state,
        "process_returncode": returncode,
        "cli_login_authenticated_flag": _cli_login_authenticated,
        "transcript_tail": transcript_lines[-3:],
        "auth_status": _provider_auth_status_details(provider),
    }


def _terminate_cli_login_process() -> None:
    global _cli_login_process, _cli_login_transcript_path, _cli_login_provider
    global _cli_login_local_port, _cli_login_oauth_state, _cli_login_pty_master_fd
    if _cli_login_process and _cli_login_process.poll() is None:
        _cli_login_process.kill()
        try:
            _cli_login_process.wait(timeout=5)
        except Exception:
            pass
    if _cli_login_pty_master_fd is not None:
        try:
            os.close(_cli_login_pty_master_fd)
        except OSError:
            pass
    _cli_login_process = None
    _cli_login_transcript_path = None
    _cli_login_provider = None
    _cli_login_local_port = None
    _cli_login_oauth_state = None
    _cli_login_pty_master_fd = None


def _discover_cli_login_port() -> int | None:
    """Find the port Claude CLI's local OAuth callback server is listening on.

    Strategy: parse /proc/net/tcp for all TCP LISTEN sockets on 127.0.0.1,
    exclude known service ports, and return the remaining one.  In a Docker
    container the process list is small, so this is reliable.  Falls back to
    PID-based matching via /proc/<pid>/fd, then ss(8).
    """
    if not _cli_login_process or _cli_login_process.poll() is not None:
        return None
    import re as _re

    # Known ports to ignore (our own services)
    KNOWN_PORTS = {8081, 8090, 8080, 8082, 8083, 8000, 3000, 53, 631, 11434}

    # --- Method 1: Scan /proc/net/tcp AND /proc/net/tcp6 for LISTEN sockets ---
    # Claude CLI (Node.js) may bind on IPv6 ::1 instead of IPv4 127.0.0.1,
    # especially inside Docker containers.  Check both.
    try:
        candidate_ports: list[int] = []
        # IPv4 localhost hex representations
        _IPV4_LOCALHOST = {"0100007F", "00000000"}
        # IPv6 localhost (::1) in /proc/net/tcp6 format
        _IPV6_LOCALHOST = {
            "00000000000000000000000001000000",  # ::1
            "00000000000000000000000000000000",  # ::
        }
        for tcp_path in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(tcp_path) as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 4:
                            continue
                        if parts[3] != "0A":  # 0A = LISTEN
                            continue
                        local = parts[1]
                        ip_hex, port_hex = local.split(":")
                        if ip_hex not in _IPV4_LOCALHOST and ip_hex not in _IPV6_LOCALHOST:
                            continue
                        port = int(port_hex, 16)
                        if port not in KNOWN_PORTS and port not in candidate_ports:
                            candidate_ports.append(port)
            except FileNotFoundError:
                continue

        # If there's exactly one unknown listening port, that's our target.
        # If multiple, try PID-based filtering below.
        if len(candidate_ports) == 1:
            return candidate_ports[0]

        # Multiple candidates — try to narrow via PID fd matching
        if candidate_ports:
            # Build inode → port map (check both tcp and tcp6)
            inode_to_port: dict[int, int] = {}
            for tcp_path in ("/proc/net/tcp", "/proc/net/tcp6"):
                try:
                    with open(tcp_path) as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) < 10 or parts[3] != "0A":
                                continue
                            ip_hex, port_hex = parts[1].split(":")
                            if ip_hex not in _IPV4_LOCALHOST and ip_hex not in _IPV6_LOCALHOST:
                                continue
                            port = int(port_hex, 16)
                            if port in KNOWN_PORTS:
                                continue
                            inode_to_port[int(parts[9])] = port
                except FileNotFoundError:
                    continue

            # Walk process tree from our PID
            root_pid = _cli_login_process.pid
            pids_to_check = [root_pid]
            # Find children by scanning /proc/*/stat
            try:
                for entry in Path("/proc").iterdir():
                    if not entry.name.isdigit():
                        continue
                    stat_path = entry / "stat"
                    try:
                        stat_text = stat_path.read_text()
                        # Format: pid (comm) state ppid ...
                        m = _re.search(r"\)\s+\S+\s+(\d+)", stat_text)
                        if m and int(m.group(1)) in pids_to_check:
                            pids_to_check.append(int(entry.name))
                    except (OSError, PermissionError):
                        continue
            except (OSError, PermissionError):
                pass

            for pid in pids_to_check:
                fd_dir = Path(f"/proc/{pid}/fd")
                if not fd_dir.exists():
                    continue
                try:
                    for fd in fd_dir.iterdir():
                        try:
                            target = os.readlink(str(fd))
                        except (OSError, PermissionError):
                            continue
                        m = _re.match(r"socket:\[(\d+)\]", target)
                        if m:
                            inode = int(m.group(1))
                            if inode in inode_to_port:
                                return inode_to_port[inode]
                except (OSError, PermissionError):
                    continue

            # Still multiple candidates — return the highest port (most likely
            # to be the ephemeral one Claude picked)
            return max(candidate_ports)
    except Exception:
        pass

    # --- Method 2: Fallback to ss (not available in all Docker images) ---
    try:
        result = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "claude" in line or "node" in line:
                m = _re.search(r"127\.0\.0\.1:(\d+)", line)
                if m:
                    port = int(m.group(1))
                    if port not in KNOWN_PORTS:
                        return port
    except Exception:
        pass

    return None


def _extract_oauth_state(auth_url: str) -> str | None:
    """Extract the state parameter from an OAuth URL."""
    if not auth_url:
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)
        states = params.get("state", [])
        return states[0] if states else None
    except Exception:
        return None


def _read_cli_transcript_lines(path: str | None) -> list[str]:
    if not path:
        return []
    transcript = Path(path)
    if not transcript.exists():
        return []
    return [line.strip() for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def _attempt_claude_login_via_transcript(cmd: list[str]) -> tuple[str | None, list[str]]:
    """Start Claude CLI login using a PTY so the Ink TUI works.

    Uses pty.openpty() to give the CLI a real terminal, which is required
    for the interactive 'Paste code here' prompt.  The PTY master fd is
    stored in _cli_login_pty_master_fd so _submit_code_via_pty() can
    write the auth code later.
    """
    global _cli_login_process, _cli_login_transcript_path, _cli_login_pty_master_fd
    import pty as _pty
    import select as _select_mod

    # Create a PTY pair
    master_fd, slave_fd = _pty.openpty()
    _cli_login_pty_master_fd = master_fd

    # Also keep a transcript file for debug
    transcript_dir = tempfile.mkdtemp(prefix="jane-cli-login-")
    transcript_path = Path(transcript_dir) / "claude-auth.log"
    _cli_login_transcript_path = str(transcript_path)

    _cli_login_process = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "200", "LINES": "40"},
    )
    os.close(slave_fd)

    # Read output from the PTY master, looking for the auth URL
    auth_url = None
    raw_output = b""
    output_lines: list[str] = []
    url_pattern = re.compile(r"https?://\S+")
    deadline = time.time() + 30

    while time.time() < deadline:
        ready, _, _ = _select_mod.select([master_fd], [], [], 0.5)
        if ready:
            try:
                data = os.read(master_fd, 8192)
                raw_output += data
            except OSError:
                break

        # Strip ANSI codes and extract text
        clean = re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', raw_output)
        clean = re.sub(rb'\x1b\][^\x07]*\x07', b'', clean)
        clean = re.sub(rb'\x1b\]8;[^\x1b]*\x1b\\\\?', b'', clean)
        text = clean.decode("utf-8", errors="replace")
        output_lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Write transcript for debugging
        transcript_path.write_text(text, encoding="utf-8")

        # Look for URL
        for line in output_lines:
            match = url_pattern.search(line)
            if match:
                candidate = match.group(0).rstrip(")").rstrip("\\")
                if "claude.com" in candidate or "anthropic.com" in candidate:
                    auth_url = candidate
                    break
        if auth_url:
            break
        if _cli_login_process.poll() is not None:
            break

    return auth_url, output_lines


_cli_login_device_code: str | None = None  # For OpenAI device-auth flow

def _attempt_cli_login_command(cmd: list[str]) -> tuple[str | None, list[str]]:
    global _cli_login_process, _cli_login_device_code
    if cmd[0] == "claude":
        return _attempt_claude_login_via_transcript(cmd)

    _cli_login_device_code = None
    _cli_login_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "TERM": "dumb"},
    )

    auth_url = None
    output_lines: list[str] = []
    deadline = time.time() + 30
    while time.time() < deadline:
        if _cli_login_process.poll() is not None:
            break
        ready, _, _ = _select.select([_cli_login_process.stdout], [], [], 1.0)
        if not ready:
            continue
        line = _cli_login_process.stdout.readline()
        if not line:
            break
        stripped = line.strip()
        if stripped:
            output_lines.append(stripped)
        # Extract URL
        if not auth_url:
            for word in line.split():
                if word.startswith("http://") or word.startswith("https://"):
                    auth_url = word.strip().rstrip(")")
                    break
        # Extract device code (e.g. "MMVV-CSOZV" — uppercase with dash)
        if auth_url and not _cli_login_device_code:
            device_match = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4,6})\b", stripped)
            if device_match:
                _cli_login_device_code = device_match.group(1)
        # Stop once we have both URL and device code (or just URL for non-device flows)
        if auth_url and (_cli_login_device_code or time.time() > deadline - 25):
            # Read a bit more to catch the device code if it comes shortly after
            if not _cli_login_device_code:
                extra_deadline = time.time() + 3
                while time.time() < extra_deadline:
                    ready2, _, _ = _select.select([_cli_login_process.stdout], [], [], 0.5)
                    if ready2:
                        line2 = _cli_login_process.stdout.readline()
                        if line2:
                            stripped2 = line2.strip()
                            if stripped2:
                                output_lines.append(stripped2)
                            dm = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4,6})\b", stripped2)
                            if dm:
                                _cli_login_device_code = dm.group(1)
                                break
            break
    return auth_url, output_lines


@app.post("/api/cli-login")
async def cli_login(request: Request):
    """Start CLI login process and return the auth URL."""
    global _cli_login_process, _cli_login_authenticated, _cli_login_provider
    global _cli_login_local_port, _cli_login_oauth_state
    body = await request.json()
    provider = body.get("provider", os.environ.get("JANE_BRAIN", "gemini"))

    # Kill any previous login process
    _terminate_cli_login_process()
    _cli_login_authenticated = False
    _cli_login_provider = provider

    cmd_candidates = _cli_login_candidates(provider)
    if not cmd_candidates:
        return JSONResponse({"error": f"Unknown provider: {provider}"})

    import shutil as _shutil
    cli_bin = _cli_binary_for_provider(provider)
    if not cli_bin or not _shutil.which(cli_bin):
        return JSONResponse({"error": f"CLI '{cli_bin or provider}' is not installed yet. The first-boot installer may still be running — please wait a minute and try again."})

    if _provider_auth_status(provider):
        _cli_login_authenticated = True
        return JSONResponse({"auth_url": None, "already_authenticated": True})

    # --- Claude: self-managed OAuth (no dependency on CLI's callback server) ---
    if provider == "claude":
        import hashlib as _hashlib
        global _claude_oauth_verifier, _claude_oauth_state
        _claude_oauth_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        _claude_oauth_state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        code_challenge = base64.urlsafe_b64encode(
            _hashlib.sha256(_claude_oauth_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        from urllib.parse import urlencode as _urlencode
        auth_url = "https://claude.com/cai/oauth/authorize?" + _urlencode({
            "code": "true",
            "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
            "response_type": "code",
            "redirect_uri": "https://platform.claude.com/oauth/code/callback",
            "scope": "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers user:file_upload",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": _claude_oauth_state,
        })
        return JSONResponse({"auth_url": auth_url})

    # --- Gemini: self-managed Google OAuth ---
    if provider == "gemini":
        import hashlib as _hashlib
        global _gemini_oauth_verifier, _gemini_oauth_state
        _gemini_oauth_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        _gemini_oauth_state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        code_challenge = base64.urlsafe_b64encode(
            _hashlib.sha256(_gemini_oauth_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        from urllib.parse import urlencode as _urlencode
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + _urlencode({
            "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
            "response_type": "code",
            "redirect_uri": "https://codeassist.google.com/authcode",
            "access_type": "offline",
            "scope": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": _gemini_oauth_state,
        })
        return JSONResponse({"auth_url": auth_url})

    # --- Other providers: use CLI-based login ---
    try:
        last_output_lines: list[str] = []
        for cmd in cmd_candidates:
            auth_url, output_lines = _attempt_cli_login_command(cmd)
            last_output_lines = output_lines
            if auth_url:
                resp_data = {"auth_url": auth_url}
                if _cli_login_device_code:
                    resp_data["device_code"] = _cli_login_device_code
                return JSONResponse(resp_data)
            if _provider_auth_status(provider):
                _cli_login_authenticated = True
                return JSONResponse({"auth_url": None, "already_authenticated": True})
            _terminate_cli_login_process()

        tail = " | ".join(last_output_lines[-3:]) if last_output_lines else "No CLI output captured."
        return JSONResponse({"error": f"Could not get auth URL. Output: {tail}"})
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/api/cli-login/code")
async def cli_login_code(request: Request):
    """Submit a browser-returned auth code to the active CLI login session.

    For Claude: delivers the OAuth code to the CLI's local HTTP callback server
    at /callback?code=<code>&state=<state>.  The CLI uses PKCE and validates
    the state param, then exchanges the code for an auth token.
    """
    global _cli_login_authenticated, _cli_login_local_port
    body = await request.json()
    code = (body.get("code") or "").strip()
    provider = (body.get("provider") or _cli_login_provider or os.environ.get("JANE_BRAIN", "gemini")).lower()

    if not code:
        return JSONResponse({"ok": False, "error": "Authentication code is required."}, status_code=400)

    # --- Claude: self-managed OAuth token exchange ---
    if provider == "claude":
        if not _claude_oauth_verifier or not _claude_oauth_state:
            return JSONResponse({"ok": False, "error": "No active OAuth session. Click Connect Account again."}, status_code=400)

        # The code from Anthropic's callback page is "AUTH_CODE#STATE" — extract just the code
        auth_code = code.split("#")[0].strip()
        if not auth_code:
            return JSONResponse({"ok": False, "error": "Invalid code format."}, status_code=400)

        # Exchange the code for tokens at Anthropic's token endpoint
        from urllib.parse import urlencode as _urlencode
        import urllib.request as _urllib_req
        token_data = _urlencode({
            "grant_type": "authorization_code",
            "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
            "code": auth_code,
            "code_verifier": _claude_oauth_verifier,
            "redirect_uri": "https://platform.claude.com/oauth/code/callback",
        }).encode()

        try:
            token_req = _urllib_req.Request(
                "https://platform.claude.com/v1/oauth/token",
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "claude-code/2.1.86",
                    "Accept": "application/json",
                },
            )
            token_resp = _urllib_req.urlopen(token_req, timeout=15)
            tokens = json.loads(token_resp.read())
        except Exception as exc:
            last_exc = exc

        if not tokens:
            error_detail = str(last_exc)
            if hasattr(last_exc, "read"):
                try:
                    error_body = last_exc.read().decode()
                    error_json = json.loads(error_body)
                    if error_json.get("error", {}).get("type") == "rate_limit_error":
                        return JSONResponse({"ok": False, "error": "Token exchange failed: Anthropic's servers are rate-limiting requests for this application. This is a known issue. Please try again in a few minutes."}, status_code=429)
                    error_detail = error_body[:300]
                except:
                    error_detail = last_exc.read().decode()[:300]
            
            return JSONResponse({"ok": False, "error": f"Token exchange failed: {error_detail}"}, status_code=400)

        # Write credentials to Claude CLI's config file
        import shutil as _shutil
        claude_bin = _shutil.which("claude")
        # Determine the claude config directory
        claude_dir = Path.home() / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        creds_path = claude_dir / ".credentials.json"

        scopes = tokens.get("scope", "").split(" ") if tokens.get("scope") else []
        creds = {
            "claudeAiOauth": {
                "accessToken": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
                "expiresAt": int(time.time() * 1000) + tokens.get("expires_in", 3600) * 1000,
                "scopes": scopes,
            }
        }
        creds_path.write_text(json.dumps(creds), encoding="utf-8")
        creds_path.chmod(0o600)

        # Invalidate cache for provider status
        _auth_status_cache.pop(provider, None)

        # Verify auth status
        _cli_login_authenticated = True
        if _provider_auth_status(provider):
            return JSONResponse({"ok": True, "authenticated": True})
        else:
            # Credentials written but status check failed — still OK
            return JSONResponse({"ok": True, "authenticated": True, "note": "Credentials saved, status check pending"})

    # --- Gemini: self-managed Google OAuth token exchange ---
    if provider == "gemini":
        if not _gemini_oauth_verifier or not _gemini_oauth_state:
            return JSONResponse({"ok": False, "error": "No active OAuth session. Click Connect Account again."}, status_code=400)

        auth_code = code.strip()
        from urllib.parse import urlencode as _urlencode
        import urllib.request as _urllib_req
        token_data = _urlencode({
            "grant_type": "authorization_code",
            "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
            "client_secret": "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",
            "code": auth_code,
            "code_verifier": _gemini_oauth_verifier,
            "redirect_uri": "https://codeassist.google.com/authcode",
        }).encode()

        try:
            token_req = _urllib_req.Request(
                "https://oauth2.googleapis.com/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp = _urllib_req.urlopen(token_req, timeout=15)
            tokens = json.loads(token_resp.read())
        except Exception as exc:
            last_exc = exc

        if not tokens:
            error_detail = str(last_exc)
            if hasattr(last_exc, "read"):
                try:
                    error_body = last_exc.read().decode()
                    error_json = json.loads(error_body)
                    if "rateLimitExceeded" in error_body:
                        return JSONResponse({"ok": False, "error": "Token exchange failed: Google's servers are rate-limiting requests for this application. Please try again in a few minutes."}, status_code=429)
                    error_detail = error_body[:300]
                except:
                    error_detail = last_exc.read().decode()[:300]
            return JSONResponse({"ok": False, "error": f"Token exchange failed: {error_detail}"}, status_code=400)

        # Write credentials to Gemini CLI's config file (~/.gemini/oauth_creds.json)
        gemini_dir = Path.home() / ".gemini"
        gemini_dir.mkdir(parents=True, exist_ok=True)
        creds_path = gemini_dir / "oauth_creds.json"

        creds = {
            "type": "authorized_user",
            "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
            "client_secret": "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",
            "refresh_token": tokens.get("refresh_token", ""),
        }
        creds_path.write_text(json.dumps(creds), encoding="utf-8")
        creds_path.chmod(0o600)

        # Invalidate cache
        _auth_status_cache.pop(provider, None)

        _cli_login_authenticated = True
        return JSONResponse({"ok": True, "authenticated": True})

    # --- Other providers: need active CLI process ---
    if not _cli_login_process or _cli_login_process.poll() is not None:
        return JSONResponse({"ok": False, "error": "No active login session. Start Connect Account again."}, status_code=400)

        return JSONResponse({"ok": True, "authenticated": False, "pending": True, "debug": _cli_login_debug_snapshot(provider)})

    # --- Other providers: write code to stdin (original behavior) ---
    if not getattr(_cli_login_process, "stdin", None):
        return JSONResponse({"ok": False, "error": "This login session does not accept code entry."}, status_code=400)

    try:
        _cli_login_process.stdin.write(code + "\n")
        _cli_login_process.stdin.flush()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Could not submit authentication code: {exc}"}, status_code=500)

    deadline = time.time() + 20
    while time.time() < deadline:
        if _provider_auth_status(provider):
            _cli_login_authenticated = True
            return JSONResponse({"ok": True, "authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
        if _cli_login_process.poll() is not None:
            authenticated = _cli_login_process.returncode == 0 or _provider_auth_status(provider)
            _cli_login_authenticated = authenticated
            if authenticated:
                return JSONResponse({"ok": True, "authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
            break
        await asyncio.sleep(2.0)

    return JSONResponse({"ok": True, "authenticated": False, "pending": True, "debug": _cli_login_debug_snapshot(provider)})


@app.get("/api/cli-login/status")
async def cli_login_status():
    """Check if the CLI login completed."""
    global _cli_login_process, _cli_login_authenticated
    provider = (_cli_login_provider or os.environ.get("JANE_BRAIN", "gemini")).lower()
    if _cli_login_authenticated:
        return JSONResponse({"authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
    if _provider_auth_status(provider):
        _cli_login_authenticated = True
        return JSONResponse({"authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
    if _cli_login_process and _cli_login_process.poll() is not None:
        _cli_login_authenticated = _cli_login_process.returncode == 0 or _provider_auth_status(provider)
        return JSONResponse({"authenticated": _cli_login_authenticated, "debug": _cli_login_debug_snapshot(provider)})
    return JSONResponse({"authenticated": False, "debug": _cli_login_debug_snapshot(provider)})
