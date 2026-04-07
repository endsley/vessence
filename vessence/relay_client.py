#!/usr/bin/env python3
"""Vessence Relay Client — E2E encrypted tunnel with P2P relay support.

Runs on the user's machine. Three modes:
  1. --auto/--connect: tunnel to relay server (direct or via peer)
  2. --relay-node: volunteer as relay node for other users (sees only ciphertext)
  3. --register: register a subdomain + generate keypair

E2E encryption uses X25519 key exchange + XSalsa20-Poly1305 (via PyNaCl).
Relay nodes only forward opaque ciphertext — zero plaintext access.

Config stored in ~/.vessence-relay.json
"""

import argparse
import asyncio
import base64
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
    import nacl.public
    import nacl.utils
    import nacl.secret
    import nacl.encoding
except ImportError:
    print("Install PyNaCl for E2E encryption: pip install pynacl")
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
RELAY_NODE_WS = os.environ.get("RELAY_NODE_WS_URL", "wss://relay.vessences.com/relay-node")
LOCAL_JANE = os.environ.get("JANE_LOCAL_URL", "http://localhost:8081")
RECONNECT_DELAY = 5
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


# ── Key Management ────────────────────────────────────────────────────────────

def generate_keypair() -> tuple[str, str]:
    """Generate X25519 keypair. Returns (public_key_b64, private_key_b64)."""
    private_key = nacl.public.PrivateKey.generate()
    public_key = private_key.public_key
    return (
        base64.b64encode(public_key.encode()).decode("utf-8"),
        base64.b64encode(private_key.encode()).decode("utf-8"),
    )


def load_private_key(config: dict) -> nacl.public.PrivateKey:
    """Load private key from config."""
    raw = base64.b64decode(config["private_key"])
    return nacl.public.PrivateKey(raw)


def decrypt_request(private_key: nacl.public.PrivateKey,
                     ciphertext: bytes) -> bytes:
    """Decrypt a request from the phone.

    Format: ephemeral_pubkey (32 bytes) + nonce (24 bytes) + ciphertext
    The phone generates a new ephemeral keypair per request for forward secrecy.
    """
    if len(ciphertext) < 56:  # 32 + 24 minimum
        raise ValueError("Ciphertext too short")
    ephemeral_pub = nacl.public.PublicKey(ciphertext[:32])
    box = nacl.public.Box(private_key, ephemeral_pub)
    return box.decrypt(ciphertext[32:])


def encrypt_response(private_key: nacl.public.PrivateKey,
                      phone_pubkey_bytes: bytes,
                      plaintext: bytes) -> bytes:
    """Encrypt a response for the phone.

    Format: nonce (24 bytes) + ciphertext
    Uses the server's static private key + phone's ephemeral public key.
    """
    phone_pub = nacl.public.PublicKey(phone_pubkey_bytes)
    box = nacl.public.Box(private_key, phone_pub)
    return box.encrypt(plaintext)


# ── Registration ──────────────────────────────────────────────────────────────

async def register_interactive():
    """Register with the relay server, generating a keypair."""
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

    if not username or not password:
        print("Username and password are required.")
        sys.exit(1)

    # Generate E2E encryption keypair
    print("Generating encryption keypair...")
    pub_b64, priv_b64 = generate_keypair()

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{RELAY_API}/api/register",
            json={
                "username": username,
                "password": password,
                "public_key": pub_b64,
            },
        ) as resp:
            data = await resp.json()
            if resp.status == 201:
                config = {
                    "username": data["username"],
                    "url": data["url"],
                    "token": data["token"],
                    "public_key": pub_b64,
                    "private_key": priv_b64,
                }
                save_config(config)
                print(f"\nRegistered! Your permanent URL: {data['url']}")
                print(f"E2E encryption keypair generated and saved.")
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


# ── Direct Tunnel ─────────────────────────────────────────────────────────────

async def forward_to_jane(request_data: dict, encrypted_body: bytes | None,
                          private_key: nacl.public.PrivateKey) -> tuple[dict | None, bytes | None]:
    """Forward a request to local Jane. Handles E2E decryption/encryption.

    Returns (json_response, encrypted_bytes) — one will be None.
    """
    if request_data.get("body_encrypted") and encrypted_body:
        # Decrypt the request from the phone
        try:
            plaintext = decrypt_request(private_key, encrypted_body)
            # plaintext format: phone_ephemeral_pubkey (32) + HTTP request bytes
            phone_pub = encrypted_body[:32]
            request_json = json.loads(plaintext)
            method = request_json.get("method", request_data.get("method", "GET"))
            path = request_json.get("path", request_data.get("path", "/"))
            headers = request_json.get("headers", {})
            body = request_json.get("body", "")
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            return {"type": "response", "request_id": request_data["request_id"],
                    "status": 400, "headers": {}, "body": "Decryption failed"}, None
    else:
        # Unencrypted (backward compat or local network)
        method = request_data.get("method", "GET")
        path = request_data.get("path", "/")
        headers = request_data.get("headers", {})
        body = request_data.get("body", "")
        phone_pub = None

    url = f"{LOCAL_JANE}{path}"
    skip_headers = {"host", "connection", "upgrade", "transfer-encoding"}
    clean_headers = {k: v for k, v in headers.items() if k.lower() not in skip_headers}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, headers=clean_headers,
                data=body.encode("utf-8") if isinstance(body, str) and body else body if isinstance(body, bytes) else None,
                timeout=aiohttp.ClientTimeout(total=25),
                ssl=False,
            ) as resp:
                resp_body = await resp.read()

                if phone_pub:
                    # Encrypt response back to phone
                    response_plain = json.dumps({
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        "body": base64.b64encode(resp_body).decode("utf-8"),
                    }).encode("utf-8")
                    encrypted = encrypt_response(private_key, phone_pub, response_plain)
                    return None, encrypted
                else:
                    return {
                        "type": "response",
                        "request_id": request_data["request_id"],
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        "body": resp_body.decode("utf-8", errors="replace"),
                    }, None
    except Exception as e:
        logger.error("Error forwarding to Jane: %s", e)
        return {
            "type": "response",
            "request_id": request_data["request_id"],
            "status": 502, "headers": {"content-type": "application/json"},
            "body": json.dumps({"error": f"Local Jane server error: {e}"}),
        }, None


async def run_tunnel(config: dict):
    """Maintain persistent WebSocket tunnel to the relay server."""
    token = config["token"]
    username = config["username"]
    private_key = load_private_key(config)
    delay = RECONNECT_DELAY
    pending_bodies: dict[str, bytes] = {}  # request_id → encrypted body

    while True:
        try:
            logger.info("Connecting to relay as %s...", username)
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    RELAY_WS, heartbeat=30, max_msg_size=10 * 1024 * 1024,
                ) as ws:
                    await ws.send_json({"token": token})
                    auth_resp = await asyncio.wait_for(ws.receive_json(), timeout=10)

                    if auth_resp.get("type") == "error":
                        logger.error("Auth failed: %s", auth_resp.get("message"))
                        return

                    logger.info("Tunnel active: %s → %s", config["url"], LOCAL_JANE)
                    delay = RECONNECT_DELAY

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "request":
                                    request_id = data["request_id"]
                                    encrypted_body = pending_bodies.pop(request_id, None)
                                    json_resp, encrypted_resp = await forward_to_jane(
                                        data, encrypted_body, private_key
                                    )
                                    if encrypted_resp:
                                        # Send encrypted response as binary
                                        await ws.send_bytes(
                                            request_id.encode("utf-8") + encrypted_resp
                                        )
                                    elif json_resp:
                                        await ws.send_json(json_resp)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            # Encrypted body: first 36 bytes = request_id
                            if len(msg.data) > 36:
                                req_id = msg.data[:36].decode("utf-8", errors="replace")
                                pending_bodies[req_id] = msg.data[36:]
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


# ── P2P Relay Node Mode ──────────────────────────────────────────────────────

async def run_relay_node(config: dict):
    """Run as a relay node — forward encrypted traffic for assigned buddies.

    This node NEVER decrypts traffic. It receives ciphertext from the relay
    server and forwards it to the target user's machine via their direct
    tunnel. The relay node only sees opaque bytes.
    """
    token = config["token"]
    username = config["username"]
    delay = RECONNECT_DELAY

    # Buddy tunnels: target_username → WebSocket to their machine
    buddy_connections: dict[str, aiohttp.ClientWebSocketResponse] = {}
    pending_bodies: dict[str, bytes] = {}

    async def get_buddy_ws(target_user: str, session: aiohttp.ClientSession
                            ) -> aiohttp.ClientWebSocketResponse | None:
        """Get or create a tunnel to a buddy's machine."""
        ws = buddy_connections.get(target_user)
        if ws and not ws.closed:
            return ws
        # Look up target's tunnel info from relay
        try:
            async with session.get(f"{RELAY_API}/api/route/{target_user}") as resp:
                if resp.status != 200:
                    return None
                route = await resp.json()
                if not route.get("online"):
                    return None
        except Exception:
            return None
        return None  # relay node doesn't connect to buddies directly —
        # it forwards through the central relay's tunnel manager

    while True:
        try:
            logger.info("Connecting as relay node: %s...", username)
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    RELAY_NODE_WS, heartbeat=30, max_msg_size=10 * 1024 * 1024,
                ) as ws:
                    await ws.send_json({"token": token})
                    auth_resp = await asyncio.wait_for(ws.receive_json(), timeout=10)

                    if auth_resp.get("type") == "error":
                        logger.error("Auth failed: %s", auth_resp.get("message"))
                        return

                    logger.info("Relay node active: %s (forwarding encrypted traffic)", username)
                    delay = RECONNECT_DELAY

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "relay_request":
                                    target = data["target_user"]
                                    request_id = data["request_id"]
                                    encrypted_body = pending_bodies.pop(request_id, None)

                                    # Forward to target's local Jane via relay
                                    # The relay node connects to the target's
                                    # machine and forwards the ciphertext.
                                    logger.info(
                                        "Relaying request %s → %s (encrypted, %d bytes)",
                                        request_id[:8], target,
                                        len(encrypted_body) if encrypted_body else 0,
                                    )

                                    # For now, relay nodes forward back through
                                    # the central server which has the direct
                                    # tunnel to the target. In a future version,
                                    # relay nodes can connect directly to peers.
                                    # The important thing is: the relay node
                                    # NEVER decrypts — it just pipes bytes.
                                    try:
                                        async with session.ws_connect(
                                            RELAY_WS, heartbeat=30,
                                        ) as target_ws:
                                            await target_ws.send_json({"token": token})
                                            await asyncio.wait_for(
                                                target_ws.receive_json(), timeout=5
                                            )
                                            # Forward the request
                                            await target_ws.send_json(data)
                                            if encrypted_body:
                                                await target_ws.send_bytes(
                                                    request_id.encode() + encrypted_body
                                                )
                                            # Wait for response
                                            resp_msg = await asyncio.wait_for(
                                                target_ws.receive(), timeout=25
                                            )
                                            # Forward response back
                                            if resp_msg.type == aiohttp.WSMsgType.BINARY:
                                                await ws.send_bytes(resp_msg.data)
                                            elif resp_msg.type == aiohttp.WSMsgType.TEXT:
                                                await ws.send_str(resp_msg.data)
                                    except Exception as e:
                                        logger.warning("Relay forward failed for %s: %s", target, e)
                                        await ws.send_json({
                                            "type": "response",
                                            "request_id": request_id,
                                            "status": 502,
                                            "body": f"Relay forward failed: {e}",
                                        })
                            except json.JSONDecodeError:
                                pass
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            if len(msg.data) > 36:
                                req_id = msg.data[:36].decode("utf-8", errors="replace")
                                pending_bodies[req_id] = msg.data[36:]
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                            break

        except aiohttp.ClientError as e:
            logger.warning("Connection lost: %s", e)
        except asyncio.TimeoutError:
            logger.warning("Connection timed out")
        except Exception as e:
            logger.warning("Relay node error: %s", e)

        logger.info("Reconnecting in %ds...", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, MAX_RECONNECT_DELAY)


# ── Main ──────────────────────────────────────────────────────────────────────

async def async_main(args):
    if args.register:
        await register_interactive()
        if not args.connect and not args.auto and not args.relay_node:
            return

    if args.auth:
        await authenticate()
        if not args.connect and not args.auto and not args.relay_node:
            return

    config = load_config()

    if args.auto and not config.get("token"):
        config = await register_interactive()

    if not config.get("token"):
        print("Not registered yet. Run with --register first.")
        sys.exit(1)

    if args.relay_node:
        # Run as relay node AND direct tunnel simultaneously
        await asyncio.gather(
            run_tunnel(config),
            run_relay_node(config),
        )
    elif args.connect or args.auto:
        await run_tunnel(config)


def main():
    parser = argparse.ArgumentParser(description="Vessence Relay Client")
    parser.add_argument("--register", action="store_true",
                        help="Register a new subdomain + generate keypair")
    parser.add_argument("--auth", action="store_true",
                        help="Re-authenticate to get a new token")
    parser.add_argument("--connect", action="store_true",
                        help="Connect tunnel to relay")
    parser.add_argument("--auto", action="store_true",
                        help="Register if needed, then connect")
    parser.add_argument("--relay-node", action="store_true",
                        help="Also volunteer as relay node for other users")
    parser.add_argument("--local-url", default=LOCAL_JANE,
                        help=f"Local Jane URL (default: {LOCAL_JANE})")
    args = parser.parse_args()

    if args.local_url != LOCAL_JANE:
        global LOCAL_JANE
        LOCAL_JANE = args.local_url

    if not any([args.register, args.auth, args.connect, args.auto, args.relay_node]):
        parser.print_help()
        sys.exit(1)

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
