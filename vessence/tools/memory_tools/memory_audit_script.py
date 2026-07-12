
import chromadb
from chromadb.utils import embedding_functions
import sqlite3
import json
import os
from datetime import datetime

# Configuration
DB_PATHS = {
    "user_memories": "/home/chieh/ambient/vessence-data/vector_db",
    "long_term_knowledge": "/home/chieh/ambient/vessence-data/vector_db/long_term_memory",
    "short_term_memory": "/home/chieh/ambient/vessence-data/vector_db/short_term_memory",
    "file_index_memories": "/home/chieh/ambient/vessence-data/vector_db/file_index_memory"
}
LEDGER_PATH = "/home/chieh/ambient/vault/conversation_history_ledger.db"

# Query pairs (original intent vs what we search for)
AUDIT_QUERIES = [
    {"query": "llm model indicator font size and location", "intent": "Show which model is running in the chat bubble"},
    {"query": "intermediary step font size", "intent": "Increase the size of the thinking steps text"},
    {"query": "refresh page jane_proxy", "intent": "Need to refresh for backend/frontend changes to take effect"},
    {"query": "audit web jane speed suggestions", "intent": "5 suggestions for increasing speed and reducing token waste"},
    {"query": "zombie hooks", "intent": "Check for stale or hanging subprocesses/hooks"},
    {"query": "memory quality audit", "intent": "Compare long-term memory to actual transcript"}
]

# Initialize Chroma Clients
ef = embedding_functions.ONNXMiniLM_L6_V2()

def audit():
    results = {}
    
    for db_name, db_path in DB_PATHS.items():
        if not os.path.exists(db_path):
            print(f"Skipping {db_name}, path not found: {db_path}")
            continue
            
        client = chromadb.PersistentClient(path=db_path)
        try:
            # For collections, we need to know the name. 
            # In user_memories, it's 'user_memories'.
            # In others, it might be different.
            collections = client.list_collections()
            if not collections:
                continue
            
            collection = client.get_collection(name=collections[0].name)
            print(f"\n--- Auditing Collection: {collections[0].name} ({db_name}) ---")
            
            for q in AUDIT_QUERIES:
                search_results = collection.query(
                    query_texts=[q["query"]],
                    n_results=3
                )
                
                print(f"Query: '{q['query']}'")
                found = False
                for i in range(len(search_results['documents'][0])):
                    doc = search_results['documents'][0][i]
                    meta = search_results['metadatas'][0][i]
                    dist = search_results['distances'][0][i]
                    
                    if dist < 1.0: # Threshold for 'relevant'
                        print(f"  [Match {i+1}] (Dist: {dist:.4f})")
                        print(f"  Text: {doc[:200]}...")
                        print(f"  Metadata: {meta}")
                        found = True
                if not found:
                    print("  [No strong matches found]")
        except Exception as e:
            print(f"Error auditing {db_name}: {e}")

if __name__ == "__main__":
    audit()
