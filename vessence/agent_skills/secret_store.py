import os
import json
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from jane.config import VESSENCE_DATA_HOME, VAULT_ENC_PATH, CHALLENGE_PATH

logger = logging.getLogger(__name__)

VAULT_PATH = VAULT_ENC_PATH
# CHALLENGE_PATH is already imported
SIGNATURE_PATH = os.path.join(VESSENCE_DATA_HOME, "data", ".node_signature")

class SecretStore:
    _instance = None
    _secrets = {}
    _unlocked = False
    _key = None
    _salt = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretStore, cls).__new__(cls)
            # Auto-unlock if signature exists
            cls._instance._auto_unlock()
        return cls._instance

    def _auto_unlock(self):
        """Attempts to unlock using the hidden signature file on disk."""
        if self._unlocked:
            return
        if os.path.exists(SIGNATURE_PATH):
            try:
                with open(SIGNATURE_PATH, "r") as f:
                    sig = f.read().strip()
                if sig:
                    self.unlock(sig)
            except Exception:
                pass

    def is_unlocked(self):
        return self._unlocked

    def unlock(self, passphrase):
        """
        Derives key from passphrase using stored salt and attempts to decrypt the vault.
        """
        if not os.path.exists(VAULT_PATH):
            logger.warning(f"Vault file not found at {VAULT_PATH}.")
            return False

        try:
            with open(VAULT_PATH, "r") as f:
                data = json.load(f)
            
            salt = base64.b64decode(data["salt"])
            encrypted_blob = base64.b64decode(data["blob"])
            
            key = self._derive_key(passphrase, salt)
            f_fernet = Fernet(key)
            
            decrypted_data = f_fernet.decrypt(encrypted_blob)
            self._secrets = json.loads(decrypted_data)
            self._key = key
            self._salt = salt
            self._unlocked = True
            logger.info("SecretStore unlocked successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to unlock SecretStore: {e}")
            self._unlocked = False
            self._key = None
            self._salt = None
            self._secrets = {}
            return False

    def initialize(self, passphrase, question):
        """
        Creates a new vault and challenge.
        """
        salt = os.urandom(16)
        self._salt = salt
        self._key = self._derive_key(passphrase, salt)
        self._secrets = {}
        self._unlocked = True
        
        # Save vault
        self._save()
        
        # Save challenge
        challenge_salt = os.urandom(16)
        answer_hash = self._hash_answer(passphrase, challenge_salt)
        
        challenge_data = {
            "question": question,
            "salt": base64.b64encode(challenge_salt).decode('utf-8'),
            "hash": base64.b64encode(answer_hash).decode('utf-8')
        }
        
        os.makedirs(os.path.dirname(CHALLENGE_PATH), exist_ok=True)
        with open(CHALLENGE_PATH, "w") as f:
            json.dump(challenge_data, f, indent=2)
        
        # Save hidden signature
        os.makedirs(os.path.dirname(SIGNATURE_PATH), exist_ok=True)
        with open(SIGNATURE_PATH, "w") as f:
            f.write(passphrase.strip())
        
        logger.info("SecretStore initialized and signature saved.")

    def lock(self):
        self._secrets = {}
        self._key = None
        self._salt = None
        self._unlocked = False
        logger.info("SecretStore locked.")

    def get(self, key, default=None):
        if not self._unlocked:
            raise RuntimeError("SecretStore is locked. Unlock it before accessing secrets.")
        return self._secrets.get(key, default)

    def set(self, key, value):
        if not self._unlocked:
            raise RuntimeError("SecretStore is locked. Unlock it before setting secrets.")
        self._secrets[key] = value
        self._save()

    def _save(self):
        if not self._key or not self._salt:
            raise RuntimeError("Cannot save vault without an active key and salt.")
        
        f_fernet = Fernet(self._key)
        encrypted_blob = f_fernet.encrypt(json.dumps(self._secrets).encode())
        
        data = {
            "salt": base64.b64encode(self._salt).decode('utf-8'),
            "blob": base64.b64encode(encrypted_blob).decode('utf-8')
        }
        
        with open(VAULT_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _derive_key(self, passphrase, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.strip().lower().encode()))

    def _hash_answer(self, answer, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
            backend=default_backend()
        )
        return kdf.derive(answer.strip().lower().encode())

    def get_challenge_question(self):
        if not os.path.exists(CHALLENGE_PATH):
            return None
        with open(CHALLENGE_PATH, "r") as f:
            data = json.load(f)
        return data.get("question")

    def verify_answer(self, answer):
        """
        Quick check against the stored hash. 
        Note: The actual security comes from trying to decrypt the vault.
        """
        if not os.path.exists(CHALLENGE_PATH):
            return False
        
        with open(CHALLENGE_PATH, "r") as f:
            data = json.load(f)
        
        salt = base64.b64decode(data["salt"])
        stored_hash = base64.b64decode(data["hash"])
        
        computed_hash = self._hash_answer(answer, salt)
        return computed_hash == stored_hash
