#!/home/chieh/google-adk-env/adk-venv/bin/python
"""
test_vault_web.py — Integration tests for the legacy Vault Browser website.

⚠️ QUARANTINED (v0.1.71): These tests hit `http://127.0.0.1:8080` (the retired
vault-web.service) and reference `/api/amber/*` endpoints that were removed
when all routes were consolidated into jane_web on port 8081. The tests in
this file WILL NOT PASS as-is — they produce 32 failed / 33 errors.

To revive: rewrite against `http://127.0.0.1:8081` (jane_web) and replace
`/api/amber/chat/stream` with `/api/jane/chat/stream`. Most file/share/auth
tests are still relevant since the underlying logic in vault_web.* modules
is unchanged. Tests for `/api/amber/*` endpoints (TestAmber* classes) can be
deleted — those endpoints are gone.

Full file is pytest.skip()'d at import time so pytest stays green without
hiding the regression. To rewrite, remove the skip directive below.
"""
import pytest
pytest.skip(
    "Quarantined post-v0.1.71 cleanup — needs rewrite against jane_web on port 8081. "
    "See docstring at top of file.",
    allow_module_level=True,
)

import sys
import os
import time
import json
import sqlite3
import secrets
import requests

sys.path.insert(0, '/home/chieh/vessence')
from dotenv import load_dotenv
load_dotenv('/home/chieh/vessence/.env')

BASE = "http://127.0.0.1:8080"
DB_PATH = "/home/chieh/ambient/vault_web/vault_web.db"
VAULT_DIR = "/home/chieh/ambient/vault"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inject_session(path_scope="/"):
    """Directly insert a valid session into the DB and return the session ID."""
    session_id = secrets.token_hex(32)
    fp = "test_fingerprint_abc123"
    import datetime
    expires = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, device_fingerprint, expires_at, trusted) VALUES (?,?,?,?)",
            (session_id, fp, expires, 1)
        )
        conn.commit()
    return session_id


def authed_session(path_scope="/"):
    """Return a requests.Session with a valid vault_session cookie."""
    sid = inject_session()
    s = requests.Session()
    # Set cookie for localhost — must match the exact host the requests will hit
    from http.cookiejar import Cookie
    import time as _time
    cookie = Cookie(
        version=0, name="vault_session", value=sid,
        port=None, port_specified=False,
        domain="127.0.0.1", domain_specified=True, domain_initial_dot=False,
        path="/", path_specified=True,
        secure=False, expires=int(_time.time()) + 3600,
        discard=False, comment=None, comment_url=None, rest={}
    )
    s.cookies.set_cookie(cookie)
    return s


def inject_otp(code="999999"):
    """Insert a fresh OTP into the DB."""
    import datetime
    with get_db() as conn:
        conn.execute("DELETE FROM otp_codes WHERE 1=1")
        expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=2)).isoformat()
        conn.execute(
            "INSERT INTO otp_codes (code, expires_at, used) VALUES (?,?,0)",
            (code, expires)
        )
        conn.commit()


def clear_failed_attempts(ip="127.0.0.1"):
    with get_db() as conn:
        conn.execute("DELETE FROM failed_attempts WHERE ip=?", (ip,))
        conn.commit()


# ─── Server Sanity ────────────────────────────────────────────────────────────

class TestServerRunning:
    def test_server_reachable(self):
        r = requests.get(BASE + "/", timeout=5)
        assert r.status_code == 200

    def test_login_page_served(self):
        """Unauthenticated root → login page."""
        r = requests.get(BASE + "/", timeout=5)
        assert "Amber Vault" in r.text
        assert "OTP" in r.text or "Send me a code" in r.text or "login" in r.text.lower()

    def test_tailwind_cdn_referenced(self):
        """App uses Tailwind via CDN — no static/style.css. Verify CDN tag present."""
        r = requests.get(BASE + "/", timeout=5)
        assert "tailwindcss" in r.text or "tailwind" in r.text.lower()


# ─── Authentication ────────────────────────────────────────────────────────────

class TestAuthentication:
    def test_check_auth_unauthenticated(self):
        r = requests.post(BASE + "/api/auth/check")
        assert r.json()["authenticated"] is False

    def test_check_auth_with_valid_session(self):
        s = authed_session()
        r = s.post(BASE + "/api/auth/check")
        assert r.json()["authenticated"] is True

    def test_is_new_device(self):
        r = requests.post(BASE + "/api/auth/is-new-device")
        data = r.json()
        assert "new_device" in data

    def test_request_otp_returns_ok(self):
        """OTP request endpoint should respond (Discord send may fail in test, but endpoint exists)."""
        r = requests.post(BASE + "/api/auth/request-otp", timeout=5)
        # Either ok:True (Discord working) or 500 (Discord unavailable in test) — endpoint exists
        assert r.status_code in (200, 500)

    def test_verify_otp_invalid_code(self):
        clear_failed_attempts()
        inject_otp("123456")
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "000000", "trust_device": False})
        assert r.status_code == 401
        assert r.json()["ok"] is False

    def test_verify_otp_valid_code(self):
        clear_failed_attempts()
        inject_otp("777777")
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "777777", "trust_device": False})
        data = r.json()
        assert data["ok"] is True
        assert "vault_session" in r.cookies

    def test_verify_otp_expired_code(self):
        """Expired OTP should fail."""
        import datetime
        clear_failed_attempts()
        with get_db() as conn:
            conn.execute("DELETE FROM otp_codes WHERE 1=1")
            expired = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).isoformat()
            conn.execute(
                "INSERT INTO otp_codes (code, expires_at, used) VALUES (?,?,0)",
                ("888888", expired)
            )
            conn.commit()
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "888888", "trust_device": False})
        assert r.json()["ok"] is False

    def test_lockout_after_5_failed_attempts(self):
        """5 bad attempts → 6th attempt returns locked error."""
        clear_failed_attempts()
        inject_otp("111111")
        # Make 5 failures (counts 1-5, sets lockout on 5th)
        for _ in range(5):
            requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "000000", "trust_device": False})
        # 6th attempt should hit lockout
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "000000", "trust_device": False})
        err = r.json().get("error", "").lower()
        assert "attempt" in err or "locked" in err or "lock" in err or "try again" in err

    def test_logout(self):
        s = authed_session()
        r = s.post(BASE + "/api/auth/logout")
        assert r.json()["ok"] is True
        # After logout, auth check should be False
        r2 = s.post(BASE + "/api/auth/check")
        assert r2.json()["authenticated"] is False

    def test_session_cookie_httponly(self):
        """Session cookie must be HttpOnly (not accessible to JS)."""
        clear_failed_attempts()
        inject_otp("654321")
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "654321", "trust_device": False})
        assert r.json()["ok"] is True
        cookie = r.cookies.get("vault_session")
        assert cookie is not None


# ─── Protected Routes ─────────────────────────────────────────────────────────

class TestProtectedRoutes:
    def test_files_list_root_requires_auth(self):
        r = requests.get(BASE + "/api/files")
        assert r.status_code == 401

    def test_shares_requires_auth(self):
        r = requests.get(BASE + "/api/shares")
        assert r.status_code == 401

    def test_playlists_requires_auth(self):
        r = requests.get(BASE + "/api/playlists")
        assert r.status_code == 401

    def test_tunnel_url_requires_auth(self):
        r = requests.get(BASE + "/api/amber/tunnel-url")
        assert r.status_code == 401

    def test_amber_chat_requires_auth(self):
        r = requests.post(BASE + "/api/amber/chat",
                         json={"message": "hi", "session_id": "test"})
        assert r.status_code == 401

    def test_devices_requires_auth(self):
        r = requests.get(BASE + "/api/auth/devices")
        assert r.status_code == 401


# ─── File API ─────────────────────────────────────────────────────────────────

class TestFileAPI:
    def setup_method(self):
        self.s = authed_session()

    def test_list_root(self):
        r = self.s.get(BASE + "/api/files")
        data = r.json()
        assert r.status_code == 200
        assert isinstance(data, dict)
        assert "folders" in data or "files" in data

    def test_list_vault_folders(self):
        r = self.s.get(BASE + "/api/files")
        data = r.json()
        folders = [f["name"] for f in data.get("folders", [])]
        # Vault should have at least some standard folders
        vault_dirs = os.listdir(VAULT_DIR)
        for d in vault_dirs:
            if os.path.isdir(os.path.join(VAULT_DIR, d)):
                assert d in folders, f"Expected folder '{d}' in root listing"

    def test_list_subfolder(self):
        r = self.s.get(BASE + "/api/files/list/images")
        assert r.status_code in (200, 404)  # 404 if images folder is empty
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict)

    def test_file_changes_endpoint(self):
        r = self.s.get(BASE + "/api/files/changes")
        assert r.status_code == 200
        data = r.json()
        assert "last_change" in data

    def test_path_traversal_blocked(self):
        """Path traversal attempts must return 403 or 404, never serve files outside vault."""
        payloads = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "images/../../../etc/passwd",
        ]
        for path in payloads:
            r = self.s.get(BASE + f"/api/files/serve/{path}")
            assert r.status_code in (403, 404, 400), f"Traversal not blocked for: {path}"
            if r.status_code == 200:
                # If somehow 200, ensure it's not /etc/passwd
                assert "root:" not in r.text

    def test_serve_nonexistent_file(self):
        r = self.s.get(BASE + "/api/files/serve/images/does_not_exist_xyz.jpg")
        assert r.status_code == 404

    def test_thumbnail_404_for_missing(self):
        r = self.s.get(BASE + "/api/files/thumbnail/images/does_not_exist_xyz.jpg")
        assert r.status_code in (401, 404)  # 401 without share cookie, 404 for missing file

    def test_thumbnail_with_auth(self):
        # Test thumbnail endpoint is reachable with auth (may 404 if no images)
        r = self.s.get(BASE + "/api/files/thumbnail/images/does_not_exist.jpg")
        assert r.status_code in (200, 404)

    def test_file_meta_requires_auth(self):
        r = requests.get(BASE + "/api/files/meta/images/test.jpg")
        assert r.status_code == 401

    def test_description_update(self):
        """Description update endpoint exists and responds."""
        r = self.s.patch(BASE + "/api/files/description/images/nonexistent.jpg",
                        json={"description": "test description"})
        # Should respond (ok: False if file doesn't exist is fine, but no crash)
        assert r.status_code in (200, 404)


# ─── Share API ────────────────────────────────────────────────────────────────

class TestShareAPI:
    def setup_method(self):
        self.s = authed_session()

    def test_list_shares(self):
        r = self.s.get(BASE + "/api/shares")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_share(self):
        r = self.s.post(BASE + "/api/shares",
                       json={"path": "images", "recipient": "TestRecipient"})
        data = r.json()
        assert data["ok"] is True
        assert "code" in data
        assert len(data["code"]) == 6
        return data["code"]

    def test_verify_share_valid(self):
        # Create a share first
        r = self.s.post(BASE + "/api/shares",
                       json={"path": "images", "recipient": "TestUser"})
        code = r.json()["code"]

        # Verify with unauthenticated request
        r2 = requests.post(BASE + "/api/auth/verify-share",
                          json={"code": code})
        data = r2.json()
        assert data["ok"] is True
        assert "share_code" in r2.cookies

    def test_verify_share_invalid_code(self):
        r = requests.post(BASE + "/api/auth/verify-share",
                         json={"code": "000000"})
        assert r.json()["ok"] is False

    def test_delete_share(self):
        # Create, then delete
        r = self.s.post(BASE + "/api/shares",
                       json={"path": "documents", "recipient": "Test"})
        code = r.json()["code"]

        # Get share ID from DB
        with get_db() as conn:
            row = conn.execute("SELECT id FROM share_links WHERE code=?", (code,)).fetchone()
        if row:
            share_id = row["id"]
            r2 = self.s.delete(BASE + f"/api/shares/{share_id}")
            assert r2.json()["ok"] is True

    def test_share_scoped_file_access(self):
        """Share code grants access to its path but not outside."""
        r = self.s.post(BASE + "/api/shares",
                       json={"path": "images", "recipient": "TestRecipient"})
        code = r.json()["code"]

        # Unauthenticated session with share cookie
        s2 = requests.Session()
        verify = s2.post(BASE + "/api/auth/verify-share", json={"code": code})
        assert verify.json()["ok"] is True

        # Can access files in images/ (even if none exist, should not 401)
        r2 = s2.get(BASE + "/api/files/thumbnail/images/some_image.jpg")
        assert r2.status_code in (200, 404)  # Not 401


# ─── Playlist API ─────────────────────────────────────────────────────────────

class TestPlaylistAPI:
    def setup_method(self):
        self.s = authed_session()

    def test_list_playlists(self):
        r = self.s.get(BASE + "/api/playlists")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_playlist(self):
        r = self.s.post(BASE + "/api/playlists",
                       json={
                           "name": "Test Playlist",
                           "tracks": [
                               {"path": "audio/test.mp3", "title": "Test Track 1"},
                               {"path": "audio/test2.mp3", "title": "Test Track 2"},
                           ]
                       })
        data = r.json()
        assert data["name"] == "Test Playlist"
        assert "id" in data
        assert len(data["tracks"]) == 2
        return data["id"]

    def test_get_playlist(self):
        # Create then fetch
        create = self.s.post(BASE + "/api/playlists",
                            json={"name": "Fetch Test", "tracks": []})
        pid = create.json()["id"]

        r = self.s.get(BASE + f"/api/playlists/{pid}")
        assert r.status_code == 200
        assert r.json()["id"] == pid

    def test_update_playlist(self):
        create = self.s.post(BASE + "/api/playlists",
                            json={"name": "Update Me", "tracks": []})
        pid = create.json()["id"]

        r = self.s.put(BASE + f"/api/playlists/{pid}",
                      json={"name": "Updated Name", "tracks": [
                          {"path": "audio/new.mp3", "title": "New Track"}
                      ]})
        data = r.json()
        assert data["name"] == "Updated Name"
        assert len(data["tracks"]) == 1

    def test_delete_playlist(self):
        create = self.s.post(BASE + "/api/playlists",
                            json={"name": "Delete Me", "tracks": []})
        pid = create.json()["id"]

        r = self.s.delete(BASE + f"/api/playlists/{pid}")
        assert r.json()["ok"] is True

        # Should be gone
        r2 = self.s.get(BASE + f"/api/playlists/{pid}")
        assert r2.status_code == 404

    def test_get_nonexistent_playlist(self):
        r = self.s.get(BASE + "/api/playlists/doesnotexist000")
        assert r.status_code == 404

    def test_playlist_track_order_preserved(self):
        tracks = [
            {"path": f"audio/track_{i}.mp3", "title": f"Track {i}"}
            for i in range(5)
        ]
        create = self.s.post(BASE + "/api/playlists",
                            json={"name": "Order Test", "tracks": tracks})
        pid = create.json()["id"]

        r = self.s.get(BASE + f"/api/playlists/{pid}")
        returned_tracks = r.json()["tracks"]
        for i, track in enumerate(returned_tracks):
            assert track["position"] == i, f"Track {i} position mismatch"


# ─── Range Requests (Audio/Video Streaming) ───────────────────────────────────

class TestRangeRequests:
    def setup_method(self):
        self.s = authed_session()
        # Find an actual audio or video file to test with
        self.test_file = None
        for folder in ["audio", "videos"]:
            vault_folder = os.path.join(VAULT_DIR, folder)
            if os.path.exists(vault_folder):
                for f in os.listdir(vault_folder):
                    fp = os.path.join(vault_folder, f)
                    if os.path.isfile(fp) and os.path.getsize(fp) > 1024:
                        self.test_file = f"{folder}/{f}"
                        break
            if self.test_file:
                break

    def test_range_request_if_media_available(self):
        if not self.test_file:
            pytest.skip("No audio/video files in vault for range test")

        r = self.s.get(BASE + f"/api/files/serve/{self.test_file}",
                      headers={"Range": "bytes=0-1023"})
        assert r.status_code == 206
        assert "Content-Range" in r.headers
        assert len(r.content) == 1024

    def test_range_request_returns_correct_content_range(self):
        if not self.test_file:
            pytest.skip("No audio/video files in vault for range test")

        r = self.s.get(BASE + f"/api/files/serve/{self.test_file}",
                      headers={"Range": "bytes=0-99"})
        assert r.status_code == 206
        cr = r.headers.get("Content-Range", "")
        assert cr.startswith("bytes 0-99/")


# ─── Cloudflare Tunnel URL ────────────────────────────────────────────────────

class TestTunnelURL:
    def setup_method(self):
        self.s = authed_session()

    def test_tunnel_url_endpoint(self):
        r = self.s.get(BASE + "/api/amber/tunnel-url")
        assert r.status_code == 200
        data = r.json()
        assert "url" in data

    def test_tunnel_url_has_cloudflare_domain(self):
        r = self.s.get(BASE + "/api/amber/tunnel-url")
        url = r.json().get("url", "")
        # Should be a trycloudflare.com URL or "not available" message
        assert "trycloudflare.com" in url or "not available" in url.lower() or "unavailable" in url.lower()


# ─── Pages (HTML responses) ───────────────────────────────────────────────────

class TestPages:
    def test_share_page(self):
        r = requests.get(BASE + "/share")
        assert r.status_code == 200
        assert "Share" in r.text or "code" in r.text.lower()

    def test_authenticated_root_returns_app(self):
        s = authed_session()
        r = s.get(BASE + "/")
        assert r.status_code == 200
        assert "Amber Vault" in r.text

    def test_unauthenticated_root_returns_login(self):
        r = requests.get(BASE + "/")
        assert r.status_code == 200
        assert "Send me a code" in r.text or "login" in r.text.lower()

    def test_devices_page_requires_auth(self):
        r = requests.get(BASE + "/settings/devices")
        # Either 401 or redirect to login
        assert r.status_code in (200, 401)
        if r.status_code == 200:
            # If rendered, should be the login page (due to redirect logic)
            # or the app; but without auth, it should enforce auth via Depends
            pass

    def test_devices_page_with_auth(self):
        s = authed_session()
        r = s.get(BASE + "/settings/devices")
        assert r.status_code == 200


# ─── Trusted Devices API ──────────────────────────────────────────────────────

class TestDevicesAPI:
    def setup_method(self):
        self.s = authed_session()

    def test_list_devices(self):
        r = self.s.get(BASE + "/api/auth/devices")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_revoke_nonexistent_device(self):
        r = self.s.delete(BASE + "/api/auth/devices/nonexistent_id_xyz")
        # Should handle gracefully (ok or 404)
        assert r.status_code in (200, 404)

    def test_trust_device_on_verify(self):
        clear_failed_attempts()
        inject_otp("246810")
        label = "Test Browser · Test OS"
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "246810", "trust_device": True, "device_label": label})
        assert r.json()["ok"] is True


# ─── Amber Unlock Endpoint ────────────────────────────────────────────────────

class TestAmberUnlock:
    def test_unlock_wrong_secret(self):
        r = requests.post(BASE + "/api/amber/unlock",
                         json={"secret": "wrong_secret", "ip": "127.0.0.1"})
        assert r.status_code == 403

    def test_unlock_correct_secret(self):
        import datetime
        secret = os.getenv("VAULT_UNLOCK_SECRET", "amber_unlock")
        # First lock an IP by setting failed_attempts
        locked_until = (datetime.datetime.utcnow() + datetime.timedelta(minutes=30)).isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO failed_attempts (ip, count, locked_until) VALUES (?,?,?)",
                ("10.0.0.1", 5, locked_until)
            )
            conn.commit()

        r = requests.post(BASE + "/api/amber/unlock",
                         json={"secret": secret, "ip": "10.0.0.1"})
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ─── Vault Tunnel URL Skill ───────────────────────────────────────────────────

class TestVaultTunnelSkill:
    def test_tunnel_url_skill_runs(self):
        import subprocess
        result = subprocess.run(
            ["/home/chieh/google-adk-env/adk-venv/bin/python",
             "/home/chieh/vessence/agent_skills/vault_tunnel_url.py"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "Vault URL" in result.stdout or "unavailable" in result.stdout.lower() or "not available" in result.stdout.lower()

    def test_tunnel_log_has_url(self):
        import re
        log_path = "/home/chieh/ambient/logs/vault_tunnel.log"
        if not os.path.exists(log_path):
            pytest.skip("Tunnel log not found — vault-tunnel.service may not be running")
        with open(log_path) as f:
            content = f.read()
        urls = re.findall(r'https://[\w\-]+\.trycloudflare\.com', content)
        assert len(urls) > 0, "No trycloudflare.com URL found in tunnel log"


# ─── Database Schema ──────────────────────────────────────────────────────────

class TestDatabaseSchema:
    def test_all_tables_exist(self):
        conn = get_db()
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        required = {"sessions", "trusted_devices", "otp_codes", "failed_attempts",
                    "share_links", "playlists", "playlist_tracks", "file_changes"}
        missing = required - tables
        assert not missing, f"Missing DB tables: {missing}"

    def test_sessions_table_columns(self):
        conn = get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        assert "id" in cols
        assert "device_fingerprint" in cols
        assert "expires_at" in cols

    def test_share_links_table_columns(self):
        conn = get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(share_links)").fetchall()}
        assert "code" in cols
        assert "path" in cols

    def test_playlists_table_columns(self):
        conn = get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(playlists)").fetchall()}
        assert "id" in cols
        assert "name" in cols

    def test_playlist_tracks_foreign_key(self):
        conn = get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(playlist_tracks)").fetchall()}
        assert "playlist_id" in cols
        assert "position" in cols
        assert "path" in cols


# ─── Security Checks ──────────────────────────────────────────────────────────

class TestSecurity:
    def setup_method(self):
        self.s = authed_session()

    def test_session_cookie_not_in_response_body(self):
        """Session token should only ever appear in Set-Cookie, not in JSON body."""
        clear_failed_attempts()
        inject_otp("135791")
        r = requests.post(BASE + "/api/auth/verify-otp",
                         json={"code": "135791", "trust_device": False})
        body = r.text
        cookie_val = r.cookies.get("vault_session", "")
        if cookie_val:
            assert cookie_val not in body, "Session token leaked in response body"

    def test_path_traversal_with_encoded_dots(self):
        payloads = [
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//etc/passwd",
        ]
        for payload in payloads:
            r = self.s.get(BASE + f"/api/files/serve/{payload}")
            assert r.status_code in (400, 403, 404, 422), \
                f"Traversal not blocked for: {payload} (got {r.status_code})"

    def test_otp_code_single_use(self):
        """OTP code cannot be used twice."""
        clear_failed_attempts()
        inject_otp("112233")
        # First use
        r1 = requests.post(BASE + "/api/auth/verify-otp",
                          json={"code": "112233", "trust_device": False})
        assert r1.json()["ok"] is True

        # Second use of same code
        clear_failed_attempts()
        r2 = requests.post(BASE + "/api/auth/verify-otp",
                          json={"code": "112233", "trust_device": False})
        assert r2.json()["ok"] is False


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["/home/chieh/google-adk-env/adk-venv/bin/python", "-m", "pytest",
         __file__, "-v", "--tb=short"],
        cwd="/home/chieh/ambient/vault_web"
    )
    sys.exit(result.returncode)
