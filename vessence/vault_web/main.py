#!/usr/bin/env python3
"""main.py — FastAPI vault browser application."""
import asyncio
import os
import sys
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, Cookie, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import aiofiles

import hashlib
import json
import subprocess

CODE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_ROOT))
from dotenv import load_dotenv
from jane.config import ADD_FACT_SCRIPT, ADK_VENV_PYTHON, ENV_FILE_PATH, VAULT_DIR, ESSENCES_DIR, VESSENCE_DATA_HOME

load_dotenv(ENV_FILE_PATH)

from database import init_db, get_db
from auth import (
    create_session, validate_session,
    is_device_trusted, register_trusted_device,
    get_trusted_device_by_id, get_trusted_device_by_fingerprint,
    get_session_user,
    get_trusted_devices, revoke_device,
    device_fingerprint_from_request, unlock_ip,
)
from oauth import oauth, allowed_email, build_external_url, google_oauth_configured
from files import (
    list_directory, get_file_metadata, update_description,
    generate_thumbnail, get_last_change_timestamp, safe_vault_path, is_text, TEXT_SIZE_LIMIT, get_mime,
    make_descriptive_filename, upsert_file_index_entry,
)
from share import create_share, validate_share, list_shares, revoke_share
from playlists import list_playlists, get_playlist, create_playlist, update_playlist, delete_playlist
from amber_proxy import send_message, get_tunnel_url

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Amber Vault")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "changeme"))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SESSION_COOKIE = "vault_session"
TRUSTED_DEVICE_COOKIE = "vault_trusted_device"
STATIC_DIR = BASE_DIR / "static"
MARKETING_DIR = CODE_ROOT / "marketing_site"
MARKETING_DOWNLOADS_DIR = MARKETING_DIR / "downloads"
ANDROID_VERSION = "0.0.17"
PUBLIC_RELEASE_DOWNLOADS = {
    "vessence-docker-package.zip": MARKETING_DOWNLOADS_DIR / "vessence-docker-package.zip",
    "docker-compose.yml": MARKETING_DIR / "docker-compose.yml",
    # Versioned APK is canonical; unversioned redirects to latest
    f"vessences-android-v{ANDROID_VERSION}.apk": MARKETING_DOWNLOADS_DIR / f"vessences-android-v{ANDROID_VERSION}.apk",
    "vessences-android.apk": MARKETING_DOWNLOADS_DIR / f"vessences-android-v{ANDROID_VERSION}.apk",
    "vessences-android-package.zip": MARKETING_DOWNLOADS_DIR / "vessences-android-package.zip",
}

# ─── Cache-Control middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        # Static assets: CSS, JS, images, fonts — cache at Cloudflare edge for 1 day
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.startswith("/api/"):
        # API responses: never cache (dynamic data)
        response.headers["Cache-Control"] = "no-store"
    else:
        # HTML pages: always revalidate (but allow conditional GET)
        response.headers["Cache-Control"] = "no-cache"
    return response


# ─── Init ─────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vault"}


@app.get("/sw.js")
async def service_worker():
    return FileResponse(str(STATIC_DIR / "chat-sw.js"), media_type="application/javascript")


@app.get("/manifest.webmanifest")
async def web_manifest():
    return FileResponse(str(STATIC_DIR / "amber.webmanifest"), media_type="application/manifest+json")


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def get_session_id(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE)


def require_auth(request: Request):
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
        return session_id, get_trusted_device_cookie_id(request)

    trusted_cookie_id = get_trusted_device_cookie_id(request)
    trusted_row = get_trusted_device_by_id(trusted_cookie_id) if trusted_cookie_id else None
    if trusted_row:
        return create_session(
            trusted_row["fingerprint"],
            trusted=True,
            user_id=trusted_row["label"] or _default_user_id(),
        ), trusted_row["id"]

    trusted_row = get_trusted_device_by_fingerprint(fp)
    if trusted_row:
        return create_session(
            fp,
            trusted=True,
            user_id=trusted_row["label"] or _default_user_id(),
        ), trusted_row["id"]

    return None, None


def check_share_or_auth(request: Request, path: str):
    """Allow access if authenticated OR if share_token cookie grants access to path."""
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
        response = templates.TemplateResponse(
            "app.html",
            {"request": request, "android_webview": is_android_webview_request(request)},
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "google_oauth_enabled": google_oauth_configured(),
            "compact_login": is_android_webview_request(request),
        },
    )


@app.get("/share", response_class=HTMLResponse)
async def share_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "share_mode": True, "compact_login": is_android_webview_request(request)},
    )


@app.get("/essences", response_class=HTMLResponse)
async def essences_page(request: Request, _=Depends(require_auth)):
    return FileResponse(str(STATIC_DIR / "essences.html"), media_type="text/html")


@app.get("/jane", response_class=HTMLResponse)
async def jane_page(request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        response = templates.TemplateResponse(
            "jane.html",
            {
                "request": request,
                "brain_label": "Gemini",
                "initial_session_id": None,
            },
        )
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "google_oauth_enabled": google_oauth_configured(),
            "compact_login": is_android_webview_request(request),
        },
    )


@app.get("/settings/devices", response_class=HTMLResponse)
async def devices_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "initial_tab": "settings",
            "android_webview": is_android_webview_request(request),
        },
    )


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
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
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "google_oauth_enabled": google_oauth_configured(),
            "compact_login": is_android_webview_request(request),
        },
    )


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.get("/auth/google")
async def login_google(request: Request):
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this deployment.")
    redirect_uri = build_external_url(
        request,
        str(request.app.url_path_for("auth_google_callback")),
        "VAULT_PUBLIC_BASE_URL",
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="OAuth error")
    user_info = token.get("userinfo", {})
    email = user_info.get("email", "")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    # Auto-trust the device — Google already verified the account
    if not is_device_trusted(fp):
        trusted_device_id = register_trusted_device(fp, email)
    else:
        trusted_row = get_trusted_device_by_fingerprint(fp)
        trusted_device_id = trusted_row["id"] if trusted_row else register_trusted_device(fp, email)
    session_id = create_session(fp, trusted=True, user_id=email)
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
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Google ID token")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    if not is_device_trusted(fp):
        trusted_device_id = register_trusted_device(fp, email)
    else:
        trusted_row = get_trusted_device_by_fingerprint(fp)
        trusted_device_id = trusted_row["id"] if trusted_row else register_trusted_device(fp, email)
    session_id = create_session(fp, trusted=True, user_id=email)
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
    return JSONResponse(
        {
            "ok": False,
            "error": "One-time code login has been removed. Sign in with Google instead.",
        },
        status_code=410,
    )


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    session_id = get_session_id(request)
    if session_id:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(TRUSTED_DEVICE_COOKIE)
    return {"ok": True}


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


# ─── Personality / User Settings ──────────────────────────────────────────────

@app.get("/api/settings/personality")
async def get_personality(request: Request, _=Depends(require_auth)):
    """Get the current user's personality setting and list of available personalities."""
    from agent_skills.user_manager import get_user_config, list_personalities
    session_id = get_session_id(request)
    user_id = get_session_user(session_id) or _default_user_id()
    config = get_user_config(user_id)
    return {
        "current": config.get("personality", "default"),
        "available": list_personalities(),
    }


@app.post("/api/settings/personality")
async def set_personality(request: Request, _=Depends(require_auth)):
    """Set the current user's Jane personality."""
    from agent_skills.user_manager import set_user_personality
    body = await request.json()
    personality = body.get("personality", "default")
    session_id = get_session_id(request)
    user_id = get_session_user(session_id) or _default_user_id()
    ok = set_user_personality(user_id, personality)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid personality: {personality}")
    return {"ok": True, "personality": personality}


@app.get("/api/app/latest-version")
async def latest_app_version():
    return {
        "version_code": 16,
        "version_name": ANDROID_VERSION,
        "download_url": f"/downloads/vessences-android-v{ANDROID_VERSION}.apk",
        "changelog": "Fix music playback, add Work Log screen, improve chat stability",
    }


@app.get("/downloads/{filename}")
async def download_release_artifact(filename: str):
    target = PUBLIC_RELEASE_DOWNLOADS.get(filename)
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


# ─── Files API ────────────────────────────────────────────────────────────────

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
    desc = body.get("description", "")
    ok = update_description(path, desc)
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

    from files import get_mime
    mime = get_mime(target.name)

    # Support range requests for audio/video
    range_header = request.headers.get("range")
    if range_header:
        return _range_response(target, mime, range_header)

    return FileResponse(str(target), media_type=mime)


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

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type=mime,
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )


@app.get("/api/files/changes")
async def file_changes(_=Depends(require_auth)):
    return {"last_change": get_last_change_timestamp()}


@app.get("/api/files/find")
async def find_file(name: str, _=Depends(require_auth)):
    """Search vault for a file by name; return its relative path for /api/files/serve/."""
    name = os.path.basename(name)  # strip any directory traversal
    for root, dirs, files in os.walk(VAULT_DIR):
        if name in files:
            rel = os.path.relpath(os.path.join(root, name), VAULT_DIR)
            return {"path": rel}
    raise HTTPException(status_code=404, detail="File not found in vault")


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
    content = body.get("content", "")
    async with aiofiles.open(target, "w", encoding="utf-8") as f:
        await f.write(content)
    with get_db() as conn:
        conn.execute("INSERT INTO file_changes DEFAULT VALUES")
    return {"ok": True}


# ─── Share API ────────────────────────────────────────────────────────────────

@app.get("/api/shares")
async def get_shares(_=Depends(require_auth)):
    return list_shares()


@app.post("/api/shares")
async def new_share(body: dict, _=Depends(require_auth)):
    path = body.get("path", "")
    recipient = body.get("recipient", "guest")
    code = create_share(path, recipient)
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
    name = body.get("name", "New Playlist")
    tracks = body.get("tracks", [])
    return create_playlist(name, tracks)


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


# ─── File Upload API ──────────────────────────────────────────────────────────

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

        from files import get_mime
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
        upsert_file_index_entry(rel_path, description, mime, updated_by="amber_web_upload")

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


# ─── Amber Chat API ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: str
    file_context: Optional[str] = None


@app.post("/api/amber/chat")
async def amber_chat(body: ChatMessage, request: Request):
    try:
        session_id, trusted_device_id = get_or_bootstrap_session(request)
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user_id = get_session_user(session_id) or _default_user_id()
        result = await send_message(user_id, body.session_id, body.message, body.file_context)
        response_text = result.get("text", "") if isinstance(result, dict) else str(result)
        if any(kw in response_text.lower() for kw in ["renamed", "updated", "saved", "created playlist"]):
            with get_db() as conn:
                conn.execute("INSERT INTO file_changes DEFAULT VALUES")
        response = JSONResponse({"response": response_text, "files": result.get("files", []) if isinstance(result, dict) else []})
        if get_session_id(request) != session_id:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        if trusted_device_id and get_trusted_device_cookie_id(request) != trusted_device_id:
            response.set_cookie(TRUSTED_DEVICE_COOKIE, trusted_device_id, httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 30)
        return response
    except HTTPException:
        raise
    except Exception:
        import logging
        logging.exception("amber_chat failed")
        raise


@app.post("/api/amber/chat/stream")
async def amber_chat_stream(body: ChatMessage, request: Request):
    try:
        session_id, trusted_device_id = get_or_bootstrap_session(request)
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user_id = get_session_user(session_id) or _default_user_id()

        async def event_stream():
            import logging
            status_messages = [
                "Sending your message to Amber.",
                "Amber is reading your message.",
                "Amber is checking your vault and memory.",
                "Amber is preparing a response.",
            ]
            task = asyncio.create_task(send_message(user_id, body.session_id, body.message, body.file_context))
            status_index = 0

            yield json.dumps({"type": "status", "data": status_messages[0]}) + "\n"

            while not task.done():
                await asyncio.sleep(1.25)
                if task.done():
                    break
                status_index = min(status_index + 1, len(status_messages) - 1)
                yield json.dumps({"type": "status", "data": status_messages[status_index]}) + "\n"

            try:
                result = await task
            except Exception as exc:
                logging.exception("amber_chat_stream send_message failed")
                yield json.dumps({"type": "error", "data": f"⚠️ Could not reach Amber: {exc}"}) + "\n"
                return

            try:
                text = result.get("text", "") if isinstance(result, dict) else str(result)
                files = result.get("files", []) if isinstance(result, dict) else []
                yield json.dumps({"type": "done", "data": text or "_(no response)_", "files": files}) + "\n"
            except Exception:
                logging.exception("amber_chat_stream serialization failed")
                yield json.dumps({"type": "error", "data": "⚠️ Amber response could not be serialized."}) + "\n"

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
    except HTTPException:
        raise
    except Exception:
        import logging
        logging.exception("amber_chat_stream failed before response")
        raise


@app.get("/api/amber/tunnel-url")
async def tunnel_url(_=Depends(require_auth)):
    url = get_tunnel_url()
    return {"url": url or "Tunnel URL not available yet."}


# ─── Amber webhook (for external calls) ──────────────────────────────────────

@app.post("/api/amber/unlock")
async def amber_unlock(request: Request):
    """Called by Amber to unlock the vault login."""
    # Simple secret check
    body = await request.json()
    if body.get("secret") != os.getenv("VAULT_UNLOCK_SECRET", "amber_unlock"):
        raise HTTPException(status_code=403)
    unlock_ip(body.get("ip"))
    return {"ok": True}


# ─── Essence Management API ──────────────────────────────────────────────────

from agent_skills.essence_loader import (
    load_essence,
    unload_essence,
    delete_essence,
    list_available_essences,
    list_loaded_essences,
    EssenceState,
)

# Module-level dict tracking loaded essence state for the web server
_essence_states: dict[str, EssenceState] = {}

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
async def list_essences(_=Depends(require_auth)):
    """List all available essences."""
    available = list_available_essences()
    loaded_names = list_loaded_essences()
    results = []
    for e in available:
        # Read full manifest for capabilities and preferred_model
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
            "loaded": e["name"] in loaded_names,
            "capabilities": capabilities,
            "preferred_model": preferred_model,
        })
    return results


@app.get("/api/essences/active")
async def get_active_essences(_=Depends(require_auth)):
    """Get the currently active essence(s)."""
    return {"active": _read_active_essences()}


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
        # Also remove from active list if present
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
        # Remove from active list if present
        active = _read_active_essences()
        if essence_name in active:
            active.remove(essence_name)
            _write_active_essences(active)
        return {"status": "deleted", "memory_ported": port_memory}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/essences/{essence_name}/activate")
async def activate_essence(essence_name: str, _=Depends(require_auth)):
    """Set an essence as the active one."""
    # Verify the essence exists
    available = list_available_essences()
    found = any(e["name"] == essence_name for e in available)
    if not found:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")

    _write_active_essences([essence_name])
    return {"status": "activated"}
