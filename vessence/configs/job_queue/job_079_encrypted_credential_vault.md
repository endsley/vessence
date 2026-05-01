# Job #079 — Encrypted Credential Vault

**Status:** completed
**Priority:** 2 (Medium)
**Created:** 2026-04-20

## Goal

Design and implement a centralized encrypted credential store that replaces scattered secrets in `.env`. All sensitive credentials (API keys, portal passwords, tokens) live in one encrypted file. The vault unlocks via a challenge at login time and holds decrypted values in memory for the server session.

## Background

Currently credentials are split between `vessence-data/.env` (runtime secrets) and hardcoded in files. The Water Lily Wellness portal credentials (`WATERLILY_USERNAME`, `WATERLILY_PASSWORD`) were the immediate trigger, but the pattern needs to generalize to all secrets.

The challenge: cron jobs and background tasks need credentials without interactive input. A pure "unlock at login" model would break overnight cron jobs if the server restarts.

## Spec

### Storage
- Single encrypted file: `vessence-data/vault.enc`
- Format: JSON encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
- Key derivation: PBKDF2-HMAC-SHA256(passphrase, salt, iterations=600_000)
- Salt stored alongside the encrypted blob (not secret)

### Unlock mechanism
- **Web login trigger**: after Google OAuth succeeds, Jane presents a security challenge (a question whose answer only the user knows, stored as a hash)
- **Correct answer** → derive Fernet key → decrypt vault → hold in `SecretStore` singleton for session lifetime
- **Server restart** → vault re-locks → next login re-unlocks
- **Cron job fallback**: if vault is locked when a cron job needs a credential, skip that run and log a warning (do NOT fail silently or use a plaintext fallback)

### SecretStore API
```python
store = SecretStore()
store.unlock(passphrase)          # decrypt vault into memory
store.get("WATERLILY_PASSWORD")   # read a value
store.set("WATERLILY_PASSWORD", "x")  # write and re-encrypt
store.is_unlocked()               # bool
store.lock()                      # wipe from memory
```

### Migration
1. Read all sensitive keys from `vessence-data/.env`
2. Move them into `vault.enc`
3. Leave only non-secret config in `.env` (ports, URLs, feature flags)
4. Update `kathia_schedule.py` and any other consumers to call `SecretStore.get()` instead of `os.environ`

### Security challenge setup
- First-time setup: Jane asks the user to choose a security question and answer
- Answer is stored as `PBKDF2(answer.lower().strip(), salt2)` — never plaintext
- On login: Jane asks the question, derives the key from the answer, attempts decryption
- Wrong answer: decryption fails (Fernet raises `InvalidToken`) → deny and re-ask

### What stays in `.env`
- `VESSENCE_DATA_HOME`, `VAULT_HOME` (paths)
- `JANE_BRAIN`, `JANE_PIPELINE`, feature flags
- `LOCAL_LLM_BASE_URL`, `CHROMADB_HOST/PORT` (non-secret infra config)

## Files to create/modify
- `agent_skills/secret_store.py` — `SecretStore` class
- `vault_web/auth.py` — add security challenge after Google OAuth
- `vault_web/templates/login.html` — add challenge UI
- `kathia_schedule.py` and other credential consumers — migrate to `SecretStore.get()`
- `configs/SKILLS_REGISTRY.md` — update

## Notes
- Do NOT store the master passphrase anywhere on disk
- Do NOT fall back to `.env` if vault is locked — fail loudly
- The `cryptography` library (already in venv) provides Fernet
