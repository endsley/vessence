# Job #56: Android File Attachments → Vault + Memory

Priority: 1
Status: completed
Created: 2026-03-30

## Description
When a user attaches a file (photo, document, etc.) to Jane chat on Android, it should:
1. Upload the file to the vault
2. Index it in ChromaDB (file_index collection) with proper description
3. Pass the file reference to Jane so she can discuss it
4. For images: Jane should be able to see/describe the image content

## Current State
- Android calls `/api/files/upload/single` which doesn't exist on Jane's server
- Upload fails silently, Jane never sees the file
- Vault web has `/api/files/upload/single` but Android uses Jane backend URL

## Changes Needed

### Android (ChatRepository.kt)
- Upload files to VAULT backend (not JANE) regardless of which chat is active
- After upload, pass the vault file URL + description as context to Jane

### Jane server (jane_web/main.py)
- Add `/api/files/upload/single` endpoint that proxies to vault
- OR: Have Android upload to vault directly and send file reference in chat message

### Jane brain (context_builder.py / jane_proxy.py)
- When a message includes a file attachment, fetch the file metadata
- For images: include the image in the prompt (multimodal) if the brain supports it
- Store file metadata in ChromaDB file_index with description

### Vault indexing (index_vault.py)
- Auto-index uploaded files with metadata (filename, type, size, upload date)
- For images: generate description using vision model

## Files to Modify
1. `android/.../ChatRepository.kt` — upload to vault, send reference to Jane
2. `jane_web/main.py` — add upload proxy or file reference handler
3. `jane/context_builder.py` — include file context in prompt
4. `agent_skills/index_vault.py` — auto-index uploaded files
