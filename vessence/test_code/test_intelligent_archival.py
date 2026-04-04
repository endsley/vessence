import unittest
import chromadb
import litellm
import uuid

# Configure LiteLLM to use the local Ollama model
litellm.set_verbose=False

def run_archival_process(short_term_collection_name, long_term_collection_name):
    """
    Runs the intelligent archival process.
    """
    client = chromadb.Client()

    try:
        short_term_collection = client.get_collection(name=short_term_collection_name)
        long_term_collection = client.get_collection(name=long_term_collection_name)
    except Exception as e:
        print(f"Error getting collections: {e}")
        return

    items = short_term_collection.get()
    if not items['documents']:
        client.delete_collection(name=short_term_collection_name)
        return

    for doc_id, document, metadata in zip(items['ids'], items['documents'], items['metadatas']):
        # 1. Decide to Keep or Discard
        keep_discard_prompt = f"""You are an AI assistant analyzing a memory. Decide if the memory is important and should be kept for long-term storage. The memory should be kept if it contains a directive, a decision, a new fact, or a summary of a conversation. Discard conversational filler, acknowledgements, or information that is unlikely to be useful later.

Memory: "{document}"

Respond with only 'Keep' or 'Discard'.
"""
        try:
            response = litellm.completion(
                model="ollama/qwen2.5-coder:14b",
                messages=[{"content": keep_discard_prompt, "role": "user"}],
                max_tokens=5,
            )
            decision = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM call failed for keep/discard: {e}")
            decision = "Discard" # Default to discard on error

        if decision == "Keep":
            # 2. Similarity Search
            results = long_term_collection.query(query_texts=[document], n_results=1)
            
            if results['documents'] and results['documents'][0]:
                similar_doc_id = results['ids'][0][0]
                similar_doc_text = results['documents'][0][0]
                
                # 3. Decide to Create or Merge
                create_merge_prompt = f"""You are an AI assistant responsible for organizing memories. A new memory needs to be added to the long-term store. You have found a similar existing memory. Decide whether to 'merge' the new memory with the existing one (if it's an update or correction) or 'create' a new, separate memory (if it's a distinct topic).

New Memory: "{document}"
Similar Existing Memory: "{similar_doc_text}"

Respond with only 'Merge' or 'Create'.
"""
                try:
                    response = litellm.completion(
                        model="ollama/qwen2.5-coder:14b",
                        messages=[{"content": create_merge_prompt, "role": "user"}],
                        max_tokens=5,
                    )
                    merge_decision = response.choices[0].message.content.strip()
                except Exception as e:
                    print(f"LLM call failed for create/merge: {e}")
                    merge_decision = "Create" # Default to create on error

                if merge_decision == "Merge":
                    # Perform merge: delete old, add new
                    long_term_collection.delete(ids=[similar_doc_id])
                    long_term_collection.add(
                        documents=[document],
                        metadatas=[metadata or {}],
                        ids=[str(uuid.uuid4())]
                    )
                else:
                    # Create new memory
                    long_term_collection.add(
                        documents=[document],
                        metadatas=[metadata or {}],
                        ids=[str(uuid.uuid4())]
                    )
            else:
                # No similar documents found, create new
                long_term_collection.add(
                    documents=[document],
                    metadatas=[metadata or {}],
                    ids=[str(uuid.uuid4())]
                )

    # 4. Delete the short-term collection
    client.delete_collection(name=short_term_collection_name)

class TestIntelligentArchival(unittest.TestCase):
    def setUp(self):
        """
        Set up the test environment.
        """
        self.client = chromadb.Client()
        self.long_term_name = f"test_long_term_{uuid.uuid4().hex}"
        self.short_term_name = f"test_short_term_{uuid.uuid4().hex}"

        # Create and populate long-term collection
        self.long_term_collection = self.client.create_collection(name=self.long_term_name)
        self.long_term_collection.add(
            documents=["The web server runs on port 8000."],
            metadatas=[{"source": "initial_fact"}],
            ids=["fact1"]
        )

        # Create and populate short-term collection
        self.short_term_collection = self.client.create_collection(name=self.short_term_name)
        self.short_term_collection.add(
            documents=[
                "New user directive: all backups must be encrypted.",
                "Okay, I will proceed.",
                "Decision: The web server will be moved to port 8080."
            ],
            metadatas=[
                {"type": "Keep"},
                {"type": "Discard"},
                {"type": "Merge"}
            ],
            ids=["mem1", "mem2", "mem3"]
        )

    def tearDown(self):
        """
        Clean up the test environment.
        """
        try:
            self.client.delete_collection(name=self.long_term_name)
        except Exception:
            # Collection might have been deleted in the test
            pass
        # Short term collection should be deleted by the process
        with self.assertRaises(Exception):
             self.client.get_collection(name=self.short_term_name)


    def test_the_full_process(self):
        """
        Test the full intelligent archival process.
        """
        run_archival_process(self.short_term_name, self.long_term_name)

        # Refresh collection object
        long_term_db = self.client.get_collection(self.long_term_name)
        all_memories = long_term_db.get()['documents']

        # 1. Assert "Keep" memory exists
        self.assertTrue(
            any("all backups must be encrypted" in mem for mem in all_memories),
            "The 'Keep' memory was not found in the long-term DB."
        )

        # 2. Assert "Discard" memory does not exist
        self.assertFalse(
            any("Okay, I will proceed" in mem for mem in all_memories),
            "The 'Discard' memory was found in the long-term DB."
        )
        
        # 3. Assert "Merge" happened correctly
        self.assertTrue(
            any("port 8080" in mem for mem in all_memories),
            "The new 'port 8080' memory was not found."
        )
        self.assertFalse(
            any("port 8000" in mem for mem in all_memories),
            "The old 'port 8000' memory was not deleted."
        )

        # 4. Assert short-term collection is deleted
        with self.assertRaises(Exception):
            self.client.get_collection(name=self.short_term_name)

if __name__ == '__main__':
    unittest.main()
