#!/usr/bin/env python3
"""Vessence Relay Client — connects local Jane server to the relay.

Runs on the user's machine. Registers a subdomain (once), then maintains
a persistent WebSocket tunnel to the relay server. The relay handles
Google OAuth — only the registered owner can access their subdomain.

Usage:
    python3 relay_client.py --register     # first time: pick subdomain
    python3 relay_client.py --connect      # connect tunnel
    python3 relay_client.py --auto         # register if needed, then connect

Config stored in ~/.vessence-relay.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("Install aiohttp: pip install aiohttp")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("relay-client")

# ── Configuration ─────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".vessence-relay.json"
RELAY_API = os.environ.get("RELAY_API_URL", "https://relay.vessences.com")
RELAY_WS = os.environ.get("RELAY_WS_URL", "wss://relay.vessences.com/tunnel")
LOCAL_JANE = "http://localhost:8081"
RECONNECT_DELAY = 5
MAX_RECONNECT_DELAY = 60


# ── Config File ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    fd = os.open(str(CONFIG_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)


# ── Registration ──────────────────────────────────────────────────────────────

async def register_interactive():
    """Walk the user through registration."""
    config = load_config()
    if config.get("token"):
        print(f"Already registered as: {config['username']}")
        print(f"Your URL: {config['url']}")
        resp = input("Re-register with a different name? (y/N): ").strip().lower()
        if resp != "y":
            return config

    print("\n--- Vessence Relay Registration ---")
    print("Pick a subdomain for your Jane server.")
    print("Your URL will be: https://<username>.vessences.com\n")

    username = input("Username (3-30 chars, alphanumeric): ").strip().lower()
    password = input("Password (min 6 chars, for re-auth): ").strip()
    google_email = input("Google email (for login access): ").strip().lower()

    if not username or not password or not google_email:
        print("All fields are required.")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{RELAY_API}/api/register",
            json={
                "username": username,
                "password": password,
                "google_email": google_email,
            },
        ) as resp:
            data = await resp.json()
            if resp.status == 201:
                config = {
                    "username": data["username"],
                    "url": data["url"],
                    "token": data["token"],
                    "google_email": google_email,
                }
                save_config(config)
                print(f"\nRegistered! Your permanent URL: {data['url']}")
                print(f"Login with: {google_email} (Google OAuth)")
                print(f"Config saved to {CONFIG_PATH}")
                return config
            else:
                print(f"\nRegistration failed: {data.get('error', 'Unknown error')}")
                sys.exit(1)


async def authenticate():
    """Re-authenticate to get a new tunnel token."""
    print("\n--- Re-authenticate ---")
    username = input("Username: ").strip().lower()
    password = input("Password: ").strip()

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{RELAY_API}/api/authenticate",
            json={"username": username, "password": password},
        ) as resp:
            data = await resp.json()
            if resp.status == 200:
                config = load_config()
                config.update({
                    "username": data["username"],
                    "url": data["url"],
                    "token": data["token"],
                })
                save_config(config)
                print("Authenticated. Token saved.")
                return config
            else:
                print(f"Auth failed: {data.get('error', 'Unknown error')}")
                sys.exit(1)


# ── Tunnel ────────────────────────────────────────────────────────────────────

async def forward_to_jane(request_data: dict,
                          session: aiohttp.ClientSession) -> dict:
    """Forward a proxied request to the local Jane server."""
    method = request_data.get("method", "GET")
    path = request_data.get("path", "/")
    headers = request_data.get("headers", {})
    body = request_data.get("body", "")

    url = f"{LOCAL_JANE}{path}"
    skip_headers = {"host", "connection", "upgrade", "transfer-encoding"}
    clean_headers = {k: v for k, v in headers.items()
                     if k.lower() not in skip_headers}

    try:
        async with session.request(
            method=method, url=url, headers=clean_headers,
            data=body.encode("utf-8") if body else None,
            timeout=aiohttp.ClientTimeout(total=25),
            ssl=False,
        ) as resp:
            resp_body = await resp.read()
            return {
                "type": "response",
                "request_id": request_data["request_id"],
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": resp_body.decode("utf-8", errors="replace"),
            }
    except Exception as e:
        logger.error("Error forwarding to Jane: %s", e)
        return {
            "type": "response",
            "request_id": request_data["request_id"],
            "status": 502,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"error": "Local Jane server unavailable"}),
        }


async def run_tunnel(config: dict):
    """Maintain persistent WebSocket tunnel to the relay server."""
    token = config["token"]
    username = config["username"]
    delay = RECONNECT_DELAY

    while True:
        try:
            logger.info("Connecting to relay as %s...", username)
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    RELAY_WS, heartbeat=30, max_msg_size=10 * 1024 * 1024,
                ) as ws:
                    # Authenticate with tunnel token
                    await ws.send_json({"token": token})
                    auth_resp = await asyncio.wait_for(
                        ws.receive_json(), timeout=10
                    )

                    if auth_resp.get("type") == "error":
                        logger.error("Auth failed: %s", auth_resp.get("message"))
                        logger.error("Run with --auth to re-authenticate.")
                        return

                    logger.info("Tunnel active: %s → %s", config["url"], LOCAL_JANE)
                    delay = RECONNECT_DELAY

                    # Process incoming requests from the relay
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "request":
                                    response = await forward_to_jane(data, session)
                                    await ws.send_json(response)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.ERROR,
                                         aiohttp.WSMsgType.CLOSE):
                            break

        except aiohttp.ClientError as e:
            logger.warning("Connection lost: %s", e)
        except asyncio.TimeoutError:
            logger.warning("Connection timed out")
        except Exception as e:
            logger.warning("Tunnel error: %s", e)

        logger.info("Reconnecting in %ds...", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, MAX_RECONNECT_DELAY)


# ── Main ──────────────────────────────────────────────────────────────────────

async def async_main(args):
    global LOCAL_JANE
    if args.local_url:
        LOCAL_JANE = args.local_url

    if args.register:
        await register_interactive()
        if not args.connect and not args.auto:
            return

    if args.auth:
        await authenticate()
        if not args.connect and not args.auto:
            return

    config = load_config()

    if args.auto and not config.get("token"):
        config = await register_interactive()

    if not config.get("token"):
        print("Not registered yet. Run with --register first.")
        sys.exit(1)

    if args.connect or args.auto:
        await run_tunnel(config)


def main():
    parser = argparse.ArgumentParser(description="Vessence Relay Client")
    parser.add_argument("--register", action="store_true",
                        help="Register a new subdomain")
    parser.add_argument("--auth", action="store_true",
                        help="Re-authenticate to get a new token")
    parser.add_argument("--connect", action="store_true",
                        help="Connect tunnel to relay")
    parser.add_argument("--auto", action="store_true",
                        help="Register if needed, then connect")
    parser.add_argument("--local-url", default=None,
                        help=f"Local Jane URL (default: {LOCAL_JANE})")
    args = parser.parse_args()

    if not any([args.register, args.auth, args.connect, args.auto]):
        parser.print_help()
        sys.exit(1)

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
