import httpx
import asyncio
import json
import base64
import uuid

AGENT_RUN_URL = "http://localhost:8000/run"
APP_NAME = "agent"

async def send_multimodal(client, user_id, session_id, text, file_bytes=None, mime_type=None, filename=None):
    parts = [{"text": text}]
    if file_bytes:
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode('utf-8'),
                "display_name": filename
            }
        })
    
    payload = {
        "app_name": APP_NAME,
        "user_id": user_id,
        "session_id": session_id,
        "new_message": {"parts": parts, "role": "user"}
    }
    
    resp = await client.post(AGENT_RUN_URL, json=payload, timeout=300.0)
    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text}")
        return []
    return resp.json()

def has_file(resp):
    for event in resp:
        if event.get("content"):
            for part in event["content"].get("parts", []):
                if "inline_data" in part:
                    return True
    return False

def get_text(resp):
    texts = []
    for event in resp:
        if event.get("content"):
            for part in event["content"].get("parts", []):
                if "text" in part:
                    texts.append(part["text"])
    return " ".join(texts)

async def test_1_web_search():
    print("\n--- Test 1: Web Search ---")
    async with httpx.AsyncClient() as client:
        uid = f"test_{uuid.uuid4().hex[:6]}"
        sid = "search_test"
        await client.post(f"http://localhost:8000/apps/{APP_NAME}/users/{uid}/sessions/{sid}", json={})
        resp = await send_multimodal(client, uid, sid, "What is the capital of France and what time is it there now?")
        text = get_text(resp)
        print(f"Reply: {text}")
        success = "Paris" in text
        print("✅ Test 1 Passed" if success else "❌ Test 1 Failed")
        return success

async def test_2_save_and_persistence():
    print("\n--- Test 2: File Save & Persistence ---")
    async with httpx.AsyncClient() as client:
        uid = f"test_{uuid.uuid4().hex[:6]}"
        sid1, sid2 = "save_sid", "load_sid"
        
        # 1. Save
        await client.post(f"http://localhost:8000/apps/{APP_NAME}/users/{uid}/sessions/{sid1}", json={})
        dummy_img = b"fake_jpeg_data_456"
        print("Saving 'my_pet.jpg'...")
        resp1 = await send_multimodal(client, uid, sid1, "Please save this photo of my dog.", dummy_img, "image/jpeg", "my_pet.jpg")
        
        # 2. Retrieve in NEW session
        print("Retrieving in new session...")
        await client.post(f"http://localhost:8000/apps/{APP_NAME}/users/{uid}/sessions/{sid2}", json={})
        resp2 = await send_multimodal(client, uid, sid2, "Attach the photo of my dog I just gave you.")
        
        success = has_file(resp2)
        print("✅ Test 2 Passed" if success else "❌ Test 2 Failed")
        return success

async def test_3_terminal():
    print("\n--- Test 3: Terminal Access ---")
    async with httpx.AsyncClient() as client:
        uid = f"test_{uuid.uuid4().hex[:6]}"
        sid = "term_test"
        await client.post(f"http://localhost:8000/apps/{APP_NAME}/users/{uid}/sessions/{sid}", json={})
        resp = await send_multimodal(client, uid, sid, "List the files in the current directory.")
        text = get_text(resp)
        print(f"Reply: {text}")
        success = "agent.py" in text or "vault_tools.py" in text
        print("✅ Test 3 Passed" if success else "❌ Test 3 Failed")
        return success

async def run_all():
    results = [
        await test_1_web_search(),
        await test_2_save_and_persistence(),
        await test_3_terminal()
    ]
    if all(results):
        print("\n🏆 ALL 3 INDEPENDENT TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED.")

if __name__ == "__main__":
    asyncio.run(run_all())
