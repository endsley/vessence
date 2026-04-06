import sys
import os
import logging
from pathlib import Path

# Setup paths
VESSENCE_HOME = "/home/chieh/ambient/vessence"
sys.path.insert(0, VESSENCE_HOME)

# Mock logger
logging.basicConfig(level=logging.INFO)

from memory.v1.conversation_manager import ConversationManager

def verify():
    # Use the session ID from our current conversation
    # We can find it in the ledger or just use a recent one
    import sqlite3
    db_path = "/home/chieh/ambient/vault/conversation_history_ledger.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT session_id FROM turns ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("No sessions found in ledger.")
        return
    
    session_id = row[0]
    print(f"Verifying Thematic Archivist for session: {session_id}")
    
    cm = ConversationManager(session_id=session_id)
    
    # We don't want to actually SAVE yet, just see what it generates
    # So we monkey-patch _promote_to_long_term to just print
    original_promote = cm._promote_to_long_term
    cm._promote_to_long_term = lambda content, category="General": print(f"\n[WOULD ARCHIVE - {category}]\n{content}")
    
    print("\n--- Running Thematic Archival Simulation ---\n")
    cm._thematic_archival()
    print("\n--- Simulation Complete ---")

if __name__ == "__main__":
    verify()
