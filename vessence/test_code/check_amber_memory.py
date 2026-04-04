
import sys
import os
import asyncio
sys.path.append('/home/chieh/vessence')
from agent_skills.local_vector_memory import LocalVectorMemoryService

async def check_memory():
    db_path = '/home/chieh/ambient/vector_db'
    user_id = '1476815711333646430'
    svc = LocalVectorMemoryService(db_path)
    print(f"Searching memory at {db_path} for user {user_id}...")
    try:
        res = await svc.search_memory(query='core capabilities', user_id=user_id, app_name='agent')
        if res.memories:
            for m in res.memories:
                print(f"FOUND FACT: {m.content.parts[0].text}")
        else:
            print("No matching facts found in vector DB.")
    except Exception as e:
        print(f"Error accessing memory: {e}")

if __name__ == "__main__":
    asyncio.run(check_memory())
