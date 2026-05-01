import os
import sys
import json
from pathlib import Path
import getpass

# Add VESSENCE_HOME to sys.path
VESSENCE_HOME = "/home/chieh/ambient/vessence"
sys.path.insert(0, VESSENCE_HOME)

from jane.config import ENV_FILE_PATH, VAULT_ENC_PATH
from agent_skills.secret_store import SecretStore

SECRET_KEYS = [
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "VAULT_TOTP_SECRET",
    "GOOGLE_CLIENT_SECRET",
    "CLOUDFLARE_TUNNEL_TOKEN",
    "DISCORD_TOKEN",
    "TAVILY_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_DNS_TOKEN",
    "VESSENCE_KEYSTORE_PASSWORD",
    "VESSENCE_KEY_PASSWORD",
    "WATERLILY_PASSWORD",
    "WATERLILY_USERNAME",
    "SESSION_SECRET_KEY"  # Migrating this too, we will inject it back to env at runtime if needed
]

def migrate():
    if not os.path.exists(ENV_FILE_PATH):
        print(f"Error: {ENV_FILE_PATH} not found.")
        return

    print("--- Vault Migration Tool ---")
    if os.path.exists(VAULT_ENC_PATH):
        print(f"Error: Vault already exists at {VAULT_ENC_PATH}.")
        return

    passphrase = getpass.getpass("Choose a master passphrase (will be stored in .node_signature): ")
    if not passphrase:
        print("Passphrase cannot be empty.")
        return
    
    question = input("Security question (backup if signature is lost): ")
    if not question:
        print("Question cannot be empty.")
        return

    # 1. Read .env and find secrets
    with open(ENV_FILE_PATH, "r") as f:
        lines = f.readlines()
    
    secrets = {}
    remaining_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            remaining_lines.append(line)
            continue
        
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            key = key.strip()
            val = val.strip()
            if key in SECRET_KEYS:
                secrets[key] = val
                print(f"Moving {key} to vault...")
            else:
                remaining_lines.append(line)
        else:
            remaining_lines.append(line)

    if not secrets:
        print("No secrets found to migrate.")
        return

    # 2. Initialize vault
    store = SecretStore()
    store.initialize(passphrase, question)
    for k, v in secrets.items():
        store.set(k, v)
    
    print(f"Successfully migrated {len(secrets)} secrets.")

    # 3. Update .env
    with open(ENV_FILE_PATH, "w") as f:
        f.writelines(remaining_lines)
    
    print(f"Updated {ENV_FILE_PATH} (secrets removed).")
    print("\nMigration complete. The vault will now auto-unlock at startup.")

if __name__ == "__main__":
    migrate()
