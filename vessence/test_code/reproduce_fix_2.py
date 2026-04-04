import os
import sys
import contextlib

# Approach 2: Redirect stderr during import
@contextlib.contextmanager
def silence_stderr():
    new_target = open(os.devnull, "w")
    old_target = sys.stderr
    sys.stderr = new_target
    try:
        yield new_target
    finally:
        sys.stderr = old_target

with silence_stderr():
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
