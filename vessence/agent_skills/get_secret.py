import sys
import os

# Add VESSENCE_HOME to sys.path
VESSENCE_HOME = "/home/chieh/ambient/vessence"
sys.path.insert(0, VESSENCE_HOME)

from agent_skills.secret_store import SecretStore

def main():
    if len(sys.argv) < 2:
        print("Usage: python get_secret.py <KEY_NAME>")
        sys.exit(1)
    
    key_name = sys.argv[1]
    store = SecretStore()
    
    if not store.is_unlocked():
        # Silently fail or print error to stderr so it doesn't mess up shell backticks
        print("Error: SecretStore is locked.", file=sys.stderr)
        sys.exit(1)
        
    val = store.get(key_name)
    if val:
        print(val)
    else:
        print(f"Error: Key '{key_name}' not found.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
