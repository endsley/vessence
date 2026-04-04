import httpx
import asyncio
import json

AGENT_RUN_URL = "http://localhost:8000/run"
APP_NAME = "agent"

async def test_direct_send_file():
    async with httpx.AsyncClient() as client:
        user_id = "test_mm"
        session_id = "test_send_file_direct"
        
        # 1. Ensure session exists
        url_session = f"http://localhost:8000/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
        await client.post(url_session, json={})

        # 2. Force tool call by asking specifically
        print("\nUser: Call tool vault_send_file with filename 'user:selfie.jpg'")
        payload_run = {
            "app_name": APP_NAME,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {
                "parts": [{"text": "Call tool vault_send_file with filename 'user:selfie.jpg'"}],
                "role": "user"
            }
        }
        resp = await client.post(AGENT_RUN_URL, json=payload_run, timeout=120.0)
        
        if resp.status_code == 200:
            data = resp.json()
            events = data if isinstance(data, list) else data.get("events", [])
            for event in events:
                author = event.get("author")
                content = event.get("content")
                if content:
                    for part in content.get("parts", []):
                        if "text" in part:
                            print(f"[{author}]: {part['text']}")
                        if "function_call" in part:
                            print(f"[{author} CALL]: {part['function_call']['name']}({part['function_call'].get('args', {})})")
                        if "inline_data" in part:
                            print(f"[{author} FILE]: Sent data ({len(part['inline_data']['data'])} bytes)")
        else:
            print(f"Error {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_direct_send_file())
