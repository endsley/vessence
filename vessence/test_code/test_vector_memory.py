import chromadb
import os

db_path = "/home/chieh/ambient/vector_db"
client = chromadb.PersistentClient(path=db_path)

# ADK v2 typically uses a collection named 'memories'
try:
    collection = client.get_collection(name="user_memories")
    
    # Search for spouse
    results = collection.query(
        query_texts=["wife spouse"],
        n_results=5
    )
    
    print("Vector Memory Search Results for 'spouse':")
    if results['documents'] and results['documents'][0]:
        for doc in results['documents'][0]:
            print(f"- {doc}")
    else:
        print("No matches found.")

except Exception as e:
    print(f"Error accessing collection: {e}")
