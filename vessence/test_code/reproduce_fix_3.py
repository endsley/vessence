import os
import sys
import contextlib

# Approach 3: Redirect FD 2 (stderr) at the OS level during import
@contextlib.contextmanager
def silence_stderr_fd():
    stderr_fd = sys.stderr.fileno()
    with os.fdopen(os.dup(stderr_fd), 'w') as old_stderr:
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), stderr_fd)
            try:
                yield
            finally:
                os.dup2(old_stderr.fileno(), stderr_fd)

with silence_stderr_fd():
    import chromadb

def test_search():
    client = chromadb.PersistentClient(path="/home/chieh/ambient/vector_db")
    try:
        collection = client.get_collection(name="user_memories")
        # The noise might also happen during the query if it loads the model then
        with silence_stderr_fd():
            results = collection.query(
                query_texts=["test"],
                n_results=1
            )
        print("Search successful")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
