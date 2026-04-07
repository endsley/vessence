import chromadb
import uuid
import sys
from pathlib import Path

import os
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jane.config import get_chroma_client, VECTOR_DB_USER_MEMORIES

db_path = VECTOR_DB_USER_MEMORIES
client = get_chroma_client(path=db_path)
collection = client.get_collection(name="user_memories")

new_facts = [
    # Personal identity facts are stored in ChromaDB user_memories.
    # This script is no longer needed — use add_fact.py instead.
]

for fact in new_facts:
    collection.add(
        documents=[fact],
        ids=[str(uuid.uuid4())],
        metadatas=[{"author": "system", "category": "identity_correction"}]
    )

print(f"Successfully updated shared memory with {len(new_facts)} clarified facts.")
