
import chromadb
import os
import re

# Silence onnxruntime noise
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

def scan_themed_memories():
    """
    Scans memories within a specific list of themes for potentially
    personal or sensitive information and prints them for review.
    """
    db_path = "/home/chieh/ambient/vessence-data/vector_db"
    if not os.path.exists(db_path):
        print(f"Database path not found: {db_path}")
        return

    # Themes provided by the user for scanning
    themes_to_scan = [
        "work", "workflow", "system", "reference", "project_architecture", 
        "preferences", "llm_config", "job_queue", "jane_preferences", 
        "jane_architecture", "identity", "feedback", "essence_registry", 
        "architecture", "docker_testing"
    ]

    # Keywords and patterns that might indicate personal info
    personal_keywords = [
        "Chieh", "Emily", "Kathia", "Water Lily Wellness", 
        "Northeastern University"
    ]
    personal_patterns = [
        re.compile(r"/home/chieh", re.IGNORECASE),
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    ]
    
    print(f"Connecting to ChromaDB at: {db_path}")
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection("user_memories")
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        return

    print(f"Scanning themes: {', '.join(themes_to_scan)}")
    questionable_memories_found = 0

    try:
        # Build the 'where' filter for ChromaDB
        where_filter = {"topic": {"$in": themes_to_scan}}
        
        results = collection.get(where=where_filter, include=["metadatas", "documents"])

        if not results['ids']:
            print("No memories found matching the specified themes.")
            return

        for i, doc_id in enumerate(results['ids']):
            doc = results['documents'][i]
            meta = results['metadatas'][i]
            
            is_questionable = False
            reason = ""

            # Check for keywords
            for keyword in personal_keywords:
                if keyword.lower() in doc.lower():
                    is_questionable = True
                    reason = f"Found keyword: '{keyword}'"
                    break
            
            if is_questionable:
                questionable_memories_found += 1
                print(f"\n--- [Questionable Memory #{questionable_memories_found}] ---")
                print(f"  ID: {doc_id}")
                print(f"  Topic: {meta.get('topic', 'N/A')}")
                print(f"  Reason: {reason}")
                print(f"  Document: {doc}")
                continue # Move to next doc once flagged

            # Check for patterns
            for pattern in personal_patterns:
                if pattern.search(doc):
                    is_questionable = True
                    reason = f"Found pattern: '{pattern.pattern}'"
                    break
            
            if is_questionable:
                questionable_memories_found += 1
                print(f"\n--- [Questionable Memory #{questionable_memories_found}] ---")
                print(f"  ID: {doc_id}")
                print(f"  Topic: {meta.get('topic', 'N/A')}")
                print(f"  Reason: {reason}")
                print(f"  Document: {doc}")

        if questionable_memories_found == 0:
            print("\nScan complete. No questionable memories found in the specified themes.")

    except Exception as e:
        print(f"An error occurred while scanning memories: {e}")

if __name__ == "__main__":
    scan_themed_memories()
