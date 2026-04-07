#!/usr/bin/env python3
"""Vessence Relay Client — connects local Jane server to the relay.

Runs on the user's machine. Registers a subdomain (once), then maintains
a persistent WebSocket tunnel to the relay server so the Android app can
reach Jane via https://username.vessences.com.

Usage:
    # First time: register and pick your subdomain
    python3 relay_client.py --register

    # After that: just connect
    python3 relay_client.py --connect

    # Or do both (register if needed, then connect)
    python3 relay_client.py --auto

Config is stored in ~/.vessence-relay.json
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

try:
    import httpx
except ImportError:
    httpx = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("relay-client")

# ── Configuration ─────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".vessence-relay.json"
RELAY_API = os.environ.get("RELAY_API_URL", "https://relay.vessences.com")
RELAY_WS = os.environ.get("RELAY_WS_URL", "wss://relay.vessences.com/tunnel")
LOCAL_JANE = os.environ.get("JANE_LOCAL_URL", "http://localhost:8081")
RECONNECT_DELAY = 5  # seconds between reconnection attempts
MAX_RECONNECT_DELAY = 60


# ── Config File ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


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
    print(f"Pick a subdomain for your Jane server.")
    print(f"Your URL will be: https://<username>.vessences.com\n")

    username = input("Username (3-30 chars, alphanumeric): ").strip().lower()
    password = input("Password (min 6 chars, for re-auth): ").strip()

    if not username or not password:
        print("Username and password are required.")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{RELAY_API}/api/register",
            json={"username": username, "password": password},
        ) as resp:
            data = await resp.json()
            if resp.status == 201:
                config = {
                    "username": data["username"],
                    "url": data["url"],
                    "token": data["token"],
                }
                save_config(config)
                print(f"\nRegistered! Your permanent URL: {data['url']}")
                print(f"Config saved to {CONFIG_PATH}")
                return config
            else:
                print(f"\nRegistration failed: {data.get('error', 'Unknown error')}")
                sys.exit(1)


async def authenticate():
    """Re-authenticate to get a new token."""
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
                config = {
                    "username": data["username"],
                    "url": data["url"],
                    "token": data["token"],
                }
                save_config(config)
                print(f"Authenticated. Token saved.")
                return config
            else:
                print(f"Auth failed: {data.get('error', 'Unknown error')}")
                sys.exit(1)


# ── Tunnel Connection ─────────────────────────────────────────────────────────

async def forward_to_jane(request_data: dict) -> dict:
    """Forward a proxied request to the local Jane server and return the response."""
    method = request_data.get("method", "GET")
    path = request_data.get("path", "/")
    headers = request_data.get("headers", {})
    body = request_data.get("body", "")

    url = f"{LOCAL_JANE}{path}"

    # Remove hop-by-hop and relay-specific headers
    skip_headers = {"host", "connection", "upgrade", "transfer-encoding"}
    clean_headers = {k: v for k, v in headers.items() if k.lower() not in skip_headers}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                headers=clean_headers,
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
            "body": json.dumps({"error": f"Local Jane server error: {e}"}),
        }


async def run_tunnel(config: dict):
    """Maintain a persistent WebSocket tunnel to the relay server."""
    token = config["token"]
    username = config["username"]
    delay = RECONNECT_DELAY

    while True:
        try:
            logger.info("Connecting to relay as %s...", username)
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    RELAY_WS,
                    heartbeat=30,
                    max_msg_size=10 * 1024 * 1024,
                ) as ws:
                    # Authenticate
                    await ws.send_json({"token": token})
                    auth_resp = await asyncio.wait_for(ws.receive_json(), timeout=10)

                    if auth_resp.get("type") == "error":
                        logger.error("Auth failed: %s", auth_resp.get("message"))
                        logger.error("Run with --register or --auth to fix.")
                        return

                    logger.info(
                        "Tunnel active: %s → %s",
                        config["url"], LOCAL_JANE,
                    )
                    delay = RECONNECT_DELAY  # reset on successful connection

                    # Process incoming requests
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "request":
                                    # Forward to Jane and send response back
                                    response = await forward_to_jane(data)
                                    await ws.send_json(response)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
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
    parser.add_argument("--local-url", default=LOCAL_JANE,
                        help="Local Jane URL (default: http://localhost:8081)")
    args = parser.parse_args()

    if args.local_url != LOCAL_JANE:
        global LOCAL_JANE
        LOCAL_JANE = args.local_url

    if not any([args.register, args.auth, args.connect, args.auto]):
        parser.print_help()
        sys.exit(1)

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
