#!/usr/bin/env python3
"""
index_vault.py — Scan the vault for untracked files and add them to ChromaDB memory.

Run this after manually dropping files into the vault. Amber and Jane will then
know the file exists, where it is, and what type it is.

For images: uses Gemini vision to generate a description automatically.

Usage:
    python index_vault.py              # scan all vault subdirs
    python index_vault.py --dry-run    # show what would be indexed, don't write
    python index_vault.py --no-vision  # skip Gemini image description
"""

import os
import sys
import json
import hashlib
import argparse
import mimetypes
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

os.environ["ORT_LOGGING_LEVEL"] = "3"

class _silence:
    def __enter__(self):
        self._fds = (os.dup(1), os.dup(2))
        self._null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self._null, 1); os.dup2(self._null, 2)
    def __exit__(self, *_):
        os.dup2(self._fds[0], 1); os.dup2(self._fds[1], 2)
        os.close(self._null); os.close(self._fds[0]); os.close(self._fds[1])

with _silence():
    import chromadb

import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    CHROMA_COLLECTION_FILE_INDEX,
    ENV_FILE_PATH,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    VAULT_DIR,
    VECTOR_DB_FILE_INDEX,
)

VAULT_PATH = Path(VAULT_DIR)
HASH_INDEX_PATH = VAULT_PATH / ".hash_index.json"

SKIP_FILES = {'.hash_index.json', '.DS_Store', 'Thumbs.db', 'conversation_history_ledger.db'}
SKIP_EXTENSIONS = {'.db', '.tmp', '.log', '.pyc'}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic'}
TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.rst',
    '.py', '.js', '.ts', '.jsx', '.tsx', '.sh', '.bash',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.env',
    '.csv', '.log', '.sql', '.xml', '.html', '.css',
}
READABLE_EXTENSIONS = TEXT_EXTENSIONS | {'.pdf', '.docx'}
MAX_EXTRACT_CHARS = 12000


# ─── ChromaDB ─────────────────────────────────────────────────────────────────

def get_collection():
    with _silence():
        client = chromadb.PersistentClient(path=VECTOR_DB_FILE_INDEX)
        return client.get_or_create_collection(
            name=CHROMA_COLLECTION_FILE_INDEX,
            metadata={"hnsw:space": "cosine"}
        )


def is_already_tracked(collection, filepath: str) -> bool:
    """Check if this file path already exists in ChromaDB."""
    results = collection.query(
        query_texts=[f"vault file {filepath}"],
        n_results=5,
        where={"topic": "vault_file"},
    )
    for doc in results['documents'][0]:
        if filepath in doc:
            return True
    return False


def add_to_chromadb(collection, filepath: str, description: str, file_type: str, dry_run: bool):
    if dry_run:
        print(f"  [DRY RUN] Would index: {filepath}")
        return
    metadata = {
        "user_id": os.environ.get("USER_NAME", "user"),
        "author": "index_vault",
        "topic": "file_index",
        "subtopic": file_type,
        "memory_type": "file_index",
        "timestamp": datetime.utcnow().isoformat(),
        "path": filepath,
    }
    collection.add(
        documents=[description],
        ids=[str(uuid.uuid4())],
        metadatas=[metadata],
    )


# ─── Hash Index ───────────────────────────────────────────────────────────────

def load_hash_index() -> dict:
    if HASH_INDEX_PATH.exists():
        try:
            return json.loads(HASH_INDEX_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_hash_index(index: dict):
    HASH_INDEX_PATH.write_text(json.dumps(index, indent=2))


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ─── Gemini Vision ────────────────────────────────────────────────────────────

def describe_image(path: Path) -> str:
    """Use Gemini to generate a description of an image."""
    try:
        import google.generativeai as genai
        api_key = None
        with open(ENV_FILE_PATH) as f:
            for line in f:
                if line.strip().startswith('GOOGLE_API_KEY='):
                    api_key = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
        if not api_key:
            return ""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        import PIL.Image
        img = PIL.Image.open(path)
        response = model.generate_content([
            "Describe this image in 1-2 sentences for a personal file archive. "
            "Include who/what is in it, setting, and any notable details. Be concise.",
            img
        ])
        return response.text.strip()
    except Exception as e:
        return f"Image file: {path.name}"


def _extract_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')[:MAX_EXTRACT_CHARS].strip()
    except Exception:
        return ""


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        chunks = []
        chars = 0
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            remaining = MAX_EXTRACT_CHARS - chars
            if remaining <= 0:
                break
            text = text[:remaining]
            chunks.append(text)
            chars += len(text)
        return "\n".join(chunks).strip()
    except Exception:
        return ""


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        texts = []
        chars = 0
        for node in root.iter():
            if not node.tag.endswith("}t"):
                continue
            text = (node.text or "").strip()
            if not text:
                continue
            remaining = MAX_EXTRACT_CHARS - chars
            if remaining <= 0:
                break
            text = text[:remaining]
            texts.append(text)
            chars += len(text)
        return " ".join(texts).strip()
    except Exception:
        return ""


def extract_readable_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return _extract_text_file(path)
    if ext == '.pdf':
        return _extract_pdf_text(path)
    if ext == '.docx':
        return _extract_docx_text(path)
    return ""


def _fallback_text_description(path: Path, text: str, mime_type: str) -> str:
    ext = path.suffix.lower()
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        if ext == '.pdf':
            return f"PDF document '{path.name}' was read but no extractable text was found."
        if ext == '.docx':
            return f"DOCX document '{path.name}' was read but no extractable text was found."
        return f"Readable {mime_type} file '{path.name}' appears empty or has no extractable text."

    excerpt = cleaned[:220]
    if ext in {'.py', '.js', '.ts', '.jsx', '.tsx', '.sh', '.bash', '.sql'}:
        return f"Code or script file '{path.name}'. Opening content indicates: {excerpt}"
    if ext in {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.env', '.csv', '.xml'}:
        return f"Structured text file '{path.name}'. Opening content indicates: {excerpt}"
    if ext in {'.md', '.markdown', '.rst', '.txt', '.html', '.css'}:
        return f"Text document '{path.name}'. Opening content indicates: {excerpt}"
    if ext == '.pdf':
        return f"PDF document '{path.name}'. Extracted opening content indicates: {excerpt}"
    if ext == '.docx':
        return f"DOCX document '{path.name}'. Extracted opening content indicates: {excerpt}"
    return f"Readable file '{path.name}'. Opening content indicates: {excerpt}"


def describe_readable_file(path: Path, mime_type: str, extracted_text: str) -> str:
    cleaned = re.sub(r"\s+", " ", extracted_text).strip()
    if not cleaned:
        return _fallback_text_description(path, extracted_text, mime_type)

    prompt = (
        "Describe this readable file in 1-2 sentences for a personal file archive.\n"
        "Rules:\n"
        "- Base the description only on the extracted file content and filename.\n"
        "- Mention the type of file and the main subject or purpose.\n"
        "- Be concrete and retrieval-friendly.\n"
        "- Do not invent details.\n\n"
        f"Filename: {path.name}\n"
        f"MIME type: {mime_type}\n"
        f"Extracted content:\n{cleaned[:4000]}"
    )

    try:
        import ollama
        client = ollama.Client(host=OLLAMA_BASE_URL)
        response = client.chat(
            model=LOCAL_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response["message"]["content"].strip()
        if text:
            return re.sub(r"\s+", " ", text)
    except Exception:
        pass

    return _fallback_text_description(path, cleaned, mime_type)


# ─── Main Scan ────────────────────────────────────────────────────────────────

def scan_vault(dry_run: bool = False, no_vision: bool = False):
    collection = get_collection()
    hash_index = load_hash_index()
    hash_index_updated = False

    new_count = 0
    skip_count = 0
    error_count = 0

    for subdir in sorted(VAULT_PATH.rglob('*')):
        if not subdir.is_file():
            continue

        # Skip system/hidden files
        if subdir.name in SKIP_FILES or subdir.name.startswith('.'):
            continue
        if subdir.suffix.lower() in SKIP_EXTENSIONS:
            continue

        rel_path = str(subdir.relative_to(VAULT_PATH.parent))  # e.g. my_agent/vault/images/foo.jpg
        full_path = str(subdir)
        ext = subdir.suffix.lower()
        mime_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
        file_type = mime_type.split('/')[0]  # image, audio, video, application, text
        size_kb = subdir.stat().st_size // 1024

        # Check hash index first (fast)
        try:
            file_hash = hash_file(subdir)
        except Exception as e:
            print(f"  [ERROR] Could not hash {subdir.name}: {e}")
            error_count += 1
            continue

        if file_hash in hash_index:
            skip_count += 1
            continue

        # Check ChromaDB (slower, catches renames)
        if is_already_tracked(collection, full_path):
            # Register hash for future fast checks
            if not dry_run:
                hash_index[file_hash] = {"filename": subdir.name, "path": full_path}
                hash_index_updated = True
            skip_count += 1
            continue

        # New file — generate description
        print(f"  [NEW] {rel_path} ({size_kb}KB, {mime_type})")

        if ext in IMAGE_EXTENSIONS and not no_vision:
            print(f"        Generating image description...")
            description = describe_image(subdir)
        elif ext in READABLE_EXTENSIONS:
            print(f"        Reading file and generating description...")
            extracted_text = extract_readable_text(subdir)
            description = describe_readable_file(subdir, mime_type, extracted_text)
        else:
            description = f"{file_type.capitalize()} file '{subdir.name}' stored at {full_path}. Type: {mime_type}, Size: {size_kb}KB."

        memory_text = f"Vault file: '{subdir.name}' at path {full_path}. {description} File type: {mime_type}."

        try:
            add_to_chromadb(collection, full_path, memory_text, file_type, dry_run)
            if not dry_run:
                hash_index[file_hash] = {"filename": subdir.name, "path": full_path, "description": description}
                hash_index_updated = True
            print(f"        ✓ Indexed: {description[:80]}")
            new_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to index {subdir.name}: {e}")
            error_count += 1

    if hash_index_updated and not dry_run:
        save_hash_index(hash_index)

    print(f"\nVault index complete: {new_count} new, {skip_count} already tracked, {error_count} errors.")
    return new_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index vault files into ChromaDB memory.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed without writing.")
    parser.add_argument("--no-vision", action="store_true", help="Skip Gemini image description.")
    args = parser.parse_args()

    print(f"Scanning vault at {VAULT_PATH}...")
    scan_vault(dry_run=args.dry_run, no_vision=args.no_vision)
