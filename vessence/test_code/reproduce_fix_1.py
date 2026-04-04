import os
import sys
import contextlib

# Approach 1: Set environment variable
os.environ["ONNXRUNTIME_EXECUTION_PROVIDERS"] = '["CPUExecutionProvider"]'

import chromadb

def test_search():
    client = chromadb.PersistentClient(path="/home/chieh/ambient/vector_db")
    try:
        collection = client.get_collection(name="user_memories")
        results = collection.query(
            query_texts=["test"],
            n_results=1
        )
        print("Search successful")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
