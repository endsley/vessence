
import chromadb
import os

# Silence onnxruntime noise
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

def inspect_memories():
    """
    Connects to the ChromaDB database, lists all collections,
    and prints a sample of items from each to help identify personal data.
    """
    db_path = "/home/chieh/ambient/vessence-data/vector_db"
    if not os.path.exists(db_path):
        print(f"Database path not found: {db_path}")
        return

    print(f"Connecting to ChromaDB at: {db_path}")
    
    try:
        client = chromadb.PersistentClient(path=db_path)
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        return

    try:
        collections = client.list_collections()
        if not collections:
            print("No collections found in the database.")
            return

        print("\n--- Found Collections ---")
        for collection in collections:
            print(f"- {collection.name}")

        for collection in collections:
            print(f"\n--- Inspecting Collection: {collection.name} ---")
            
            # Skip the short-term memory collection if it still exists
            if "short_term" in collection.name:
                print("Skipping short-term memory collection.")
                continue

            try:
                # Get the 5 most recently added items
                count = collection.count()
                if count == 0:
                    print("Collection is empty.")
                    continue
                
                print(f"Collection contains {count} items. Fetching a sample of 5.")
                results = collection.get(
                    limit=5,
                    include=["metadatas", "documents"]
                )

                for i, doc_id in enumerate(results['ids']):
                    doc = results['documents'][i]
                    meta = results['metadatas'][i]
                    print(f"\n[Item {i+1}]")
                    print(f"  ID: {doc_id}")
                    print(f"  Document: {doc[:250]}...") # Print first 250 chars
                    print(f"  Metadata: {meta}")

            except Exception as e:
                print(f"Could not retrieve items from collection '{collection.name}': {e}")
                
    except Exception as e:
        print(f"An error occurred while inspecting collections: {e}")

if __name__ == "__main__":
    inspect_memories()
