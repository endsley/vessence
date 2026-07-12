
import chromadb
import os

# Silence onnxruntime noise
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

def discover_themes():
    """
    Connects to ChromaDB, iterates through all memories, and extracts
    a unique set of all 'topic' values from the metadata.
    """
    db_path = "/home/chieh/ambient/vessence-data/vector_db"
    if not os.path.exists(db_path):
        print(f"Database path not found: {db_path}")
        return

    print(f"Connecting to ChromaDB at: {db_path}")
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection("user_memories")
    except Exception as e:
        print(f"Failed to connect to ChromaDB or get 'user_memories' collection: {e}")
        return

    try:
        print("Fetching all memories to discover themes...")
        # Get all items from the collection.
        # This might be slow if the DB is very large, but is necessary to find all unique themes.
        results = collection.get(include=["metadatas"])
        
        all_topics = set()
        
        if not results['metadatas']:
            print("No metadata found in the collection.")
            return

        for meta in results['metadatas']:
            topic = meta.get("topic")
            if topic:
                all_topics.add(topic)

        if not all_topics:
            print("No memories with a 'topic' in their metadata were found.")
            return

        print("\n--- Found Unique Memory Themes ---")
        for topic in sorted(list(all_topics)):
            print(f"- {topic}")
                
    except Exception as e:
        print(f"An error occurred while fetching or processing memories: {e}")

if __name__ == "__main__":
    discover_themes()
