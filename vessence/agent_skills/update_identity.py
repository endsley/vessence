import chromadb
import uuid
import sys
from pathlib import Path

import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import get_chroma_client, VECTOR_DB_USER_MEMORIES

db_path = VECTOR_DB_USER_MEMORIES
client = get_chroma_client(path=db_path)
collection = client.get_collection(name="user_memories")

new_facts = [
    "The user is a Professor of AI and Machine Learning at Northeastern University.",
    # Personal facts moved to user_profile.md under the runtime data root.
    
    "The user owns the clinic, but is not the REDACTED_PROFESSION; he is an AI/ML Professor."
]

for fact in new_facts:
    collection.add(
        documents=[fact],
        ids=[str(uuid.uuid4())],
        metadatas=[{"author": "system", "category": "identity_correction"}]
    )

print(f"Successfully updated shared memory with {len(new_facts)} clarified facts.")
