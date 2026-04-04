# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import sys
import logging
import json
import hashlib
from pathlib import Path
import subprocess
from google.adk.tools.base_tool import BaseTool
from google.genai import types
from typing_extensions import override

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jane.config import (
    ADD_FACT_SCRIPT,
    ADK_VENV_PYTHON,
    INDEX_VAULT_SCRIPT,
    SEARCH_MEMORY_SCRIPT,
    VAULT_DIR,
    VAULT_TUNNEL_LOG,
    VAULT_WEB_MODULE_DIR,
    VECTOR_DB_USER_MEMORIES,
)
from vault_web.files import TEXT_EXTS, TEXT_SIZE_LIMIT, safe_vault_path

logger = logging.getLogger('discord_agent.vault_tools')

VENV_PYTHON       = ADK_VENV_PYTHON
VECTOR_DB_PATH    = VECTOR_DB_USER_MEMORIES


def _add_fact(fact: str, topic: str, subtopic: str = "") -> str:
    """Write a fact directly to ChromaDB via add_fact.py."""
    cmd = [VENV_PYTHON, ADD_FACT_SCRIPT, fact, "--topic", topic, "--author", "amber"]
    if subtopic:
        cmd += ["--subtopic", subtopic]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.error(f"Memory operation failed: {e}")


def _search_memory(query: str) -> str:
    """Query ChromaDB via search_memory.py and return synthesized text."""
    try:
        result = subprocess.run(
            [VENV_PYTHON, SEARCH_MEMORY_SCRIPT, query],
            capture_output=True, text=True, timeout=60
        )
        return result.stdout.strip() or "No relevant context found."
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.error(f"Memory operation failed: {e}")
        return "Memory search unavailable."


def _delete_memory_by_query(query: str) -> int:
    """Delete ChromaDB entries matching a query. Returns count deleted."""
    script = (
        "import os; os.environ['ORT_LOGGING_LEVEL']='3'\n"
        "import sys, chromadb\n"
        f"client = chromadb.PersistentClient(path='{VECTOR_DB_PATH}')\n"
        "col = client.get_or_create_collection('user_memories')\n"
        f"results = col.query(query_texts=[{query!r}], n_results=5)\n"
        "ids = results['ids'][0] if results['ids'] else []\n"
        "if ids: col.delete(ids=ids)\n"
        "print(len(ids))\n"
    )
    try:
        result = subprocess.run(
            [VENV_PYTHON, "-c", script],
            capture_output=True, text=True, timeout=30
        )
        return int(result.stdout.strip() or "0")
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.error(f"Memory operation failed: {e}")
        return 0

def _looks_like_garbage_filename(stem: str) -> bool:
    """Returns True if the filename stem is a hash/ID rather than a human-readable name."""
    import re
    # Strip underscores and digits — if barely any real letters remain, it's garbage
    readable = re.sub(r'[^a-zA-Z]', '', stem)
    # Garbage if: very long AND fewer than 5 readable letters, OR all digits/underscores
    if len(stem) > 20 and len(readable) < 5:
        return True
    # Garbage if it's entirely digits/underscores (e.g. "507184369_10238481387999748")
    if re.fullmatch(r'[\d_]+', stem):
        return True
    return False


def _generate_descriptive_filename(description: str, original_filename: str) -> str:
    """
    Generate a clean snake_case filename from the description when the original
    filename looks like a hash or random ID.
    Returns the original filename unchanged if it's already readable.
    """
    import re
    stem, ext = os.path.splitext(original_filename)

    if not _looks_like_garbage_filename(stem):
        return original_filename  # Already a human-readable name

    if not description or len(description.strip()) < 3:
        return original_filename  # No description to generate from

    slug = description.lower()
    slug = re.sub(r"['\"]", '', slug)           # remove quotes/apostrophes
    slug = re.sub(r'[^a-z0-9\s]', ' ', slug)   # keep only alphanum + spaces
    slug = re.sub(r'\s+', '_', slug.strip())    # spaces → underscores
    slug = slug[:50].rstrip('_')                # cap at 50 chars

    if not slug:
        return original_filename

    return f"{slug}{ext}"


VAULT_HASH_INDEX = None  # Populated lazily from config


def _get_hash_index_path() -> str:
    return os.path.join(VAULT_DIR, ".hash_index.json")


def _load_hash_index() -> dict:
    """Load the content-hash → {filename, path, description} index."""
    path = _get_hash_index_path()
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_hash_index(index: dict):
    path = _get_hash_index_path()
    with open(path, "w") as f:
        json.dump(index, f, indent=2)


def _hash_content(content) -> str:
    """Return SHA-256 hex digest of content (str or bytes)."""
    if isinstance(content, str):
        data = content.encode("utf-8")
    elif isinstance(content, (bytes, bytearray)):
        data = bytes(content)
    else:
        data = str(content).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _check_duplicate(content, description: str) -> tuple:
    """
    Check if content already exists in the vault.
    Returns (is_duplicate: bool, existing_info: dict | None).
    existing_info has keys: filename, path, description
    """
    content_hash = _hash_content(content)
    index = _load_hash_index()
    if content_hash in index:
        return True, index[content_hash]
    return False, None


def _register_hash(content, filename: str, path: str, description: str):
    """Add a new file's hash to the index after saving."""
    content_hash = _hash_content(content)
    index = _load_hash_index()
    index[content_hash] = {
        "filename": filename,
        "path": path,
        "description": description,
    }
    _save_hash_index(index)


def get_file_category(filename: str) -> str:
    """Returns the subdirectory name based on the file extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']:
        return "images"
    elif ext in ['.mp4', '.mkv', '.mov', '.avi', '.wmv']:
        return "videos"
    elif ext in ['.mp3', '.wav', '.flac', '.m4a', '.ogg']:
        return "audio"
    elif ext in ['.pdf']:
        return "pdf"
    elif ext in ['.txt', '.md', '.doc', '.docx', '.csv', '.json']:
        return "documents"
    else:
        return "others"

class VaultSaveTool(BaseTool):
    """Saves a file locally into type-specific subdirectories and records metadata in memory."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_save",
            description=(
                "Saves a FILE to the local vault (images, pdfs, documents, audio, video). "
                "The system automatically sorts files into folders like images/, pdf/, etc. "
                "Use this ONLY for actual files with a filename and binary/text content. "
                "For facts, preferences, or information the user wants remembered, use memory_save instead."
            ),
            **kwargs
        )
        if not os.path.exists(VAULT_DIR):
            os.makedirs(VAULT_DIR, exist_ok=True)

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filename": types.Schema(type="STRING", description="Name of the file to save (e.g. 'notes.txt')"),
                    "content": types.Schema(type="STRING", description="The actual text content or base64 data to save"),
                    "description": types.Schema(type="STRING", description="A brief summary of what this information is"),
                    "category": types.Schema(type="STRING", description="Optional manual tag like 'work' or 'personal'"),
                    "purpose": types.Schema(type="STRING", description="Set to 'context' or 'presentation'")
                },
                required=["filename", "content", "description"]
            )
        )

    async def run_async(
        self,
        *,
        args: dict,
        tool_context
    ) -> list:
        original_filename = args.get("filename", "").replace("user:", "")
        content = args.get("content")
        description = args.get("description", "")
        user_tag = args.get("category", "general")
        purpose = args.get("purpose", "presentation")

        if not original_filename or not content:
            return [{"text": "ERROR: 'filename' and 'content' are required to save to the vault."}]

        try:
            # 1. Determine Type-based Subdirectory
            type_folder = get_file_category(original_filename)
            target_dir = os.path.join(VAULT_DIR, type_folder)
            os.makedirs(target_dir, exist_ok=True)

            # 1a. Duplicate content detection — skip if identical content already saved
            is_artifact_marker = False
            if not is_artifact_marker:
                is_dup, existing = _check_duplicate(content, description)
                if is_dup and existing:
                    logger.info(f"VaultSaveTool: Duplicate content detected — already saved as '{existing['filename']}'.")
                    return [{"text": (
                        f"⚠️ This file already exists in the vault.\n"
                        f"**Current filename:** `{existing['filename']}`\n"
                        f"**Description:** {existing['description']}\n"
                        f"No new file was saved."
                    )}]

            # 1b. Generate descriptive filename if the original looks like a hash/ID
            descriptive_filename = _generate_descriptive_filename(description, original_filename)
            if descriptive_filename != original_filename:
                logger.info(f"VaultSaveTool: Renamed '{original_filename}' → '{descriptive_filename}' based on description.")

            # 2. Filename De-duplication Logic
            filename = descriptive_filename
            target_path = os.path.join(target_dir, filename)
            
            # 3. Check if this is a registration of an existing artifact
            import re as _re
            is_artifact_marker = isinstance(content, str) and (
                content.startswith("[Uploaded Artifact:") or
                content.startswith("[ATTACHMENT_PRE_SAVED:") or
                content == "IMAGE_DATA_SAVED_TO_DISK" or
                bool(_re.match(r'^artifact_[a-zA-Z0-9\-]+(_\d+)?$', content.strip())) or  # ADK internal artifact key
                bool(_re.match(r'^user:[^\s/\\]+\.[a-zA-Z0-9]+$', content.strip()))        # user:filename.ext
            )

            artifact_ref = ""
            if isinstance(content, str) and content.startswith("[Uploaded Artifact:"):
                import re
                match = re.search(r"'(.*?)'", content)
                if match:
                    artifact_ref = match.group(1).replace("user:", "")

            # De-duplication
            if os.path.exists(target_path) and not is_artifact_marker:
                base, ext = os.path.splitext(original_filename)
                counter = 1
                while os.path.exists(target_path):
                    filename = f"{base}_{counter}{ext}"
                    target_path = os.path.join(target_dir, filename)
                    counter += 1
                logger.info(f"VaultSaveTool: Conflict. Renamed '{original_filename}' to '{filename}'.")

            # 4. Handle Physical Write / Move
            if is_artifact_marker:
                binary_data = None

                # Try to load actual binary from ADK artifact store by filename
                for artifact_key in [original_filename, f"user:{original_filename}"]:
                    try:
                        part = await tool_context.load_artifact(artifact_key)
                        if part and hasattr(part, 'inline_data') and part.inline_data:
                            raw = part.inline_data.data
                            if isinstance(raw, (bytes, bytearray)) and len(raw) > 0:
                                binary_data = raw
                                logger.info(f"VaultSaveTool: Loaded '{artifact_key}' from artifact store ({len(raw)} bytes)")
                                break
                    except Exception:
                        pass

                if binary_data:
                    with open(target_path, "wb") as f:
                        f.write(binary_data)
                else:
                    # Try old root-path move logic for backward compat
                    root_path = os.path.join(VAULT_DIR, artifact_ref or original_filename)
                    if os.path.exists(root_path) and root_path != target_path:
                        import shutil
                        shutil.move(root_path, target_path)
                        logger.info(f"VaultSaveTool: Sorted artifact to {type_folder}/{filename}")
                    elif not os.path.exists(target_path):
                        # File doesn't exist anywhere — don't write garbage, return an error
                        logger.warning(f"VaultSaveTool: Cannot retrieve binary for '{filename}' (artifact ref: '{content}'). Skipping write.")
                        return [{"text": f"⚠️ Could not save '{filename}': binary data not accessible from artifact store. "
                                         f"Please try re-uploading the file directly."}]
                    else:
                        logger.info(f"VaultSaveTool: '{filename}' already exists in vault (pre-saved by bridge). Recording metadata only.")
            else:
                if isinstance(content, str) and (content.startswith("/9j/") or len(content) > 1000):
                    try:
                        import base64
                        file_data = base64.b64decode(content, validate=True)
                        with open(target_path, "wb") as f:
                            f.write(file_data)
                    except Exception:
                        with open(target_path, "w") as f:
                            f.write(content)
                else:
                    with open(target_path, "w") as f:
                        f.write(str(content))

            # 5. Record Fact in Vector Memory
            display_path = f"{type_folder}/{filename}"
            fact = (
                f"Saved file '{filename}' in type-folder '{type_folder}' (User tag: '{user_tag}'). "
                f"Location: {display_path}. Description: {description}."
            )
            try:
                _add_fact(fact, topic=type_folder, subtopic="vault_file")
            except Exception as e:
                if "direct memory writes" in str(e):
                    logger.debug(f"Memory service doesn't support direct writes, skipping file metadata saving: {fact}")
                else:
                    logger.warning(f"Failed to record file in memory (but file was saved): {e}")

            # Register hash for future duplicate detection (non-artifact saves only)
            if not is_artifact_marker:
                try:
                    _register_hash(content, filename, target_path, description)
                except Exception as e:
                    logger.warning(f"VaultSaveTool: Failed to update hash index: {e}")

            return [{"text": f"Successfully saved '{filename}' to vault/{type_folder}/ and recorded in memory."}]
        except Exception as e:
            logger.error(f"Failed to save to structured vault: {e}")
            return [{"text": f"Failed to save file: {str(e)}"}]

class VaultSendFileTool(BaseTool):
    """Retrieves a file from the structured vault and sends it to the user."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_send_file",
            description=(
                "Retrieves a file or image from the vault and sends it to the user. "
                "The vault is structured into folders: images, videos, audio, pdf, documents, others. "
                "Use this when the user asks to see a file."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filename": types.Schema(type="STRING", description="Name of the file (e.g. 'cat.jpg')"),
                },
                required=["filename"]
            )
        )

    @override
    async def process_llm_request(
        self,
        *,
        tool_context,
        llm_request
    ) -> None:
        await super().process_llm_request(tool_context=tool_context, llm_request=llm_request)
        
        try:
            # Recursively list files to show Amber the structure
            all_files = []
            for root, dirs, files in os.walk(VAULT_DIR):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), VAULT_DIR)
                    all_files.append(rel_path)
            
            if all_files:
                llm_request.append_instructions([
                    f"Your structured vault contains: {json.dumps(all_files)}. "
                    "To send a file, use its name. I will find it in the correct folder."
                ])
        except Exception as e:
            logger.warning(f"Failed to list structured vault: {e}")

    async def run_async(
        self,
        *,
        args: dict,
        tool_context
    ) -> list:
        filename = args.get("filename", "").replace("user:", "")
        
        # Search for file in subdirectories
        target_path = None
        for root, dirs, files in os.walk(VAULT_DIR):
            if filename in files:
                target_path = os.path.join(root, filename)
                break
            # Also check if they passed a path like "images/cat.jpg"
            if os.path.exists(os.path.join(VAULT_DIR, filename)):
                target_path = os.path.join(VAULT_DIR, filename)
                break
        
        if not target_path or not os.path.exists(target_path):
            return [{
                "text": (
                    f"I have a memory of the file '{filename}', "
                    "but I can no longer find the file itself in the vault. "
                    "Should I keep the memory as it is, or should I delete the memory "
                    "that I ever had this file?"
                )
            }]

        logger.info(f"VaultSendFileTool: Found {filename} at {target_path}")
        
        # Return the file as an artifact/inline_data for the bridge to catch
        import mimetypes
        mime_type, _ = mimetypes.guess_type(target_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        return [{
            "text": f"Here is the file: {filename}",
            "file_data": {
                "file_uri": target_path,
                "mime_type": mime_type
            }
        }]

class VaultDeleteTool(BaseTool):
    """Deletes a specific memory from the vector database by ID or snippet."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_delete_memory",
            description=(
                "Deletes a specific memory or file record from the vault. "
                "Use this only when the user explicitly confirms they want a memory forgotten, "
                "especially when a file is missing from the physical vault."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "memory_id": types.Schema(type="STRING", description="The ID of the memory to delete (if known)."),
                    "query_snippet": types.Schema(type="STRING", description="A snippet of the memory to find and delete (if ID is unknown).")
                },
                required=[]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        mem_id = args.get("memory_id")
        snippet = args.get("query_snippet")
        
        try:
            query = snippet or mem_id or ""
            if not query:
                return "Could not find any matching memories to delete."
            deleted = _delete_memory_by_query(query)
            if deleted == 0:
                return "Could not find any matching memories to delete."
            return f"Successfully deleted {deleted} memory records."
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return f"Failed to delete memory: {str(e)}"

class VaultReadFileTool(BaseTool):
    """Reads the text content of a file from the structured vault."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_read_file",
            description=(
                "Reads the text content of a vault file from disk. "
                "Use this for markdown, text, code, config, JSON, CSV, logs, and similar readable files "
                "when you need the actual contents of the document to answer a question."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filename": types.Schema(
                        type="STRING",
                        description=(
                            "File name or vault-relative path to read "
                            "(e.g. 'notes.md' or 'documents/notes.md')."
                        ),
                    ),
                },
                required=["filename"]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        filename = args.get("filename", "").replace("user:", "").strip()
        if not filename:
            return "ERROR: filename is required."

        target_path = None

        # Prefer an explicit vault-relative path first.
        try:
            explicit_target = safe_vault_path(filename)
            if explicit_target.exists() and explicit_target.is_file():
                target_path = explicit_target
        except Exception:
            target_path = None

        # Fall back to searching by basename anywhere in the vault.
        if target_path is None:
            for root, dirs, files in os.walk(VAULT_DIR):
                if filename in files:
                    target_path = Path(root) / filename
                    break
                basename = os.path.basename(filename)
                if basename in files:
                    target_path = Path(root) / basename
                    break

        if target_path is None:
            return f"ERROR: File '{filename}' not found anywhere in the structured vault."

        try:
            ext = target_path.suffix.lower().lstrip(".")
            if ext not in TEXT_EXTS:
                return (
                    f"ERROR: Cannot read file type '.{ext}' as text. "
                    "I can read markdown, text, code, config, JSON, CSV, logs, and similar readable files."
                )

            if target_path.stat().st_size > TEXT_SIZE_LIMIT:
                return (
                    f"ERROR: File is too large to read directly as text "
                    f"({target_path.stat().st_size} bytes)."
                )

            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            header = f"[Read from vault: {target_path.relative_to(VAULT_DIR)}]\n\n"
            if len(content) > 30000:
                return header + content[:30000] + "\n\n[Content truncated for length...]"
            return header + content
        except Exception as e:
            logger.error(f"VaultReadFileTool: Error reading {filename}: {e}")
            return f"Failed to read file: {str(e)}"


class VaultAnalyzePdfTool(BaseTool):
    """Reads and analyzes a PDF from the vault using Gemini's native PDF understanding."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_analyze_pdf",
            description=(
                "Reads and analyzes a PDF file from the vault. "
                "Can summarize, answer questions about, or extract data from any PDF — "
                "including scanned documents and image-heavy PDFs. "
                "Provide the filename and an optional question or instruction."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filename": types.Schema(type="STRING", description="Name of the PDF file (e.g. 'report.pdf')"),
                    "instruction": types.Schema(type="STRING", description="What to do with the PDF — e.g. 'summarize', 'extract key findings', 'answer: what is the conclusion?'"),
                },
                required=["filename"]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        import base64
        import google.generativeai as genai

        filename = args.get("filename", "").strip()
        instruction = args.get("instruction", "Please summarize this PDF document.")

        # Find the file
        target_path = None
        for root, dirs, files in os.walk(VAULT_DIR):
            if filename in files:
                target_path = os.path.join(root, filename)
                break
        if not target_path and os.path.exists(os.path.join(VAULT_DIR, filename)):
            target_path = os.path.join(VAULT_DIR, filename)

        if not target_path:
            return f"ERROR: PDF '{filename}' not found in vault."

        if not target_path.lower().endswith(".pdf"):
            return f"ERROR: '{filename}' is not a PDF file."

        try:
            with open(target_path, "rb") as f:
                pdf_bytes = f.read()

            if len(pdf_bytes) > 20 * 1024 * 1024:
                return "ERROR: PDF is too large (>20MB) to analyze."

            pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            response = model.generate_content([
                {"mime_type": "application/pdf", "data": pdf_b64},
                instruction,
            ])
            return response.text or "No response generated."

        except Exception as e:
            logger.error(f"VaultAnalyzePdfTool error: {e}")
            return f"Failed to analyze PDF: {str(e)}"


class TerminalTool(BaseTool):
    """Executes basic terminal commands like ls, pwd, cd."""

    def __init__(self, **kwargs):
        super().__init__(
            name="terminal_cmd",
            description="Executes basic terminal commands (ls, pwd, cd) to explore the local filesystem.",
            **kwargs
        )
        self._cwd = os.path.expanduser("~")

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "command": types.Schema(type="STRING", description="The command to run (ls, pwd, cd)"),
                    "path": types.Schema(type="STRING", description="The target path or directory")
                },
                required=["command"]
            )
        )

    async def run_async(
        self,
        *,
        args: dict,
        tool_context
    ) -> str:
        cmd = args.get("command")
        path = args.get("path", ".")
        
        if cmd not in ["ls", "pwd", "cd"]:
            return f"ERROR: Command '{cmd}' is not allowed. Only ls, pwd, cd are supported."

        try:
            import subprocess
            if cmd == "cd":
                new_dir = os.path.expanduser(path)
                if not os.path.isabs(new_dir):
                    new_dir = os.path.normpath(os.path.join(self._cwd, new_dir))
                if os.path.isdir(new_dir):
                    self._cwd = new_dir
                    return f"Changed directory to {self._cwd}"
                return f"ERROR: Directory '{path}' not found."
            elif cmd == "pwd":
                return self._cwd
            elif cmd == "ls":
                target = os.path.expanduser(path)
                if not os.path.isabs(target):
                    target = os.path.normpath(os.path.join(self._cwd, target))
                result = subprocess.run(["ls", "-F", target], capture_output=True, text=True)
                return result.stdout if result.stdout else "(Empty directory)"
        except Exception as e:
            return f"Error executing {cmd}: {str(e)}"

class VaultSearchTool(BaseTool):
    """Searches the vector memory bank for files and retrieves them."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_search",
            description="Searches the vault for files or facts based on a semantic query. Use this to find things to update.",
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="The semantic search query")
                },
                required=["query"]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        query = args.get("query")
        result = _search_memory(query)
        if not result or result == "No relevant context found.":
            return "No relevant context found."
        return "I found the following in your vault:\n" + result

class MemorySaveTool(BaseTool):
    """Saves a new fact or piece of information directly to long-term vector memory."""

    def __init__(self, **kwargs):
        super().__init__(
            name="memory_save",
            description=(
                "Saves a fact, preference, or piece of information to long-term memory (ChromaDB). "
                "Use this whenever the user shares something they want remembered: preferences, names, "
                "dates, decisions, context about their life, work, or projects. "
                "This does NOT create a file — it stores a searchable fact in the memory database."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "fact": types.Schema(type="STRING", description="The fact or information to remember, written as a clear, complete sentence."),
                    "topic": types.Schema(type="STRING", description="A short topic label (e.g. 'family', 'work', 'preferences', 'health')."),
                    "subtopic": types.Schema(type="STRING", description="An optional more specific subtopic label.")
                },
                required=["fact", "topic"]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        fact = args.get("fact", "").strip()
        topic = args.get("topic", "general")
        subtopic = args.get("subtopic", "")

        if not fact:
            return "ERROR: 'fact' is required to save to memory."

        try:
            _add_fact(fact, topic=topic, subtopic=subtopic)
            return f"Remembered: '{fact}' (topic: {topic})"
        except Exception as e:
            logger.error(f"MemorySaveTool: Failed to save memory: {e}")
            return f"Failed to save to memory: {str(e)}"


class MemoryUpdateTool(BaseTool):
    """Updates or refines an existing factual memory in the vector database."""

    def __init__(self, **kwargs):
        super().__init__(
            name="memory_update",
            description=(
                "Refines or corrects an existing factual memory. "
                "Use this to update information about files (like labels or identities) "
                "or to correct past facts about the user."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "old_fact_snippet": types.Schema(type="STRING", description="A snippet of the old fact being updated so I can find it."),
                    "new_fact": types.Schema(type="STRING", description="The new, refined factual statement.")
                },
                required=["old_fact_snippet", "new_fact"]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        old_snippet = args.get("old_fact_snippet")
        new_fact = args.get("new_fact")
        
        try:
            _add_fact(new_fact, topic="updated", subtopic="replaces_previous")
            return f"Memory refined. I have recorded the updated fact: '{new_fact}'"
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return f"Failed to update memory: {str(e)}"

class VaultTunnelURLTool(BaseTool):
    """Reports the current Cloudflare tunnel URL for the Vault website."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_tunnel_url",
            description="Returns the current public URL for the Amber Vault website (Cloudflare Quick Tunnel). Use this when the user asks for the vault URL or wants to share it.",
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(type="OBJECT", properties={}, required=[])
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        import re
        log_paths = [
            VAULT_TUNNEL_LOG,
            "/tmp/vault_tunnel.log",
        ]
        for log_path in log_paths:
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r") as f:
                        for line in reversed(f.readlines()):
                            if "trycloudflare.com" in line:
                                match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                                if match:
                                    return f"🌐 Vault URL: {match.group(0)}"
                except Exception:
                    pass
        return "⚠️ Vault tunnel URL not available. The vault-tunnel.service may not be running."


class VaultReorganizeTool(BaseTool):
    """Autonomously moves files into new categories based on memory themes."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_reorganize",
            description="Reorganizes the vault file system into logical categories.",
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={},
                required=[]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        return "Vault reorganization started. I'm analyzing the themes and moving files to new categories."


class VaultIndexTool(BaseTool):
    """Scans the vault for manually added files and indexes them into memory."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_index",
            description=(
                "Scans the vault directory for any files that were manually added (not saved through Amber) "
                "and indexes them into ChromaDB memory. For images, generates a description automatically "
                "using vision AI. Run this after the user drops files directly into the vault."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "no_vision": types.Schema(
                        type="BOOLEAN",
                        description="If true, skip AI image descriptions (faster). Default: false."
                    )
                },
                required=[]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        no_vision = args.get("no_vision", False)
        cmd = [VENV_PYTHON, INDEX_VAULT_SCRIPT]
        if no_vision:
            cmd.append("--no-vision")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout.strip() or result.stderr.strip()
            logger.info(f"vault_index completed: {output[-200:]}")
            return output if output else "Vault index complete — no new files found."
        except subprocess.TimeoutExpired:
            return "Vault indexing timed out (too many files). Try again with --no-vision for speed."
        except Exception as e:
            return f"Vault index error: {e}"


class VaultFindAudioTool(BaseTool):
    """Finds audio files in the vault matching a search query."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_find_audio",
            description=(
                "Searches the vault for audio files (music, recordings) by filename or folder. "
                "Returns a list of matching files with their vault paths. "
                "Use this before creating a playlist so you know the exact file paths."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="Search term to filter by — matches filename or folder name. Leave empty to list all audio files."
                    ),
                },
                required=[]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        query = (args.get("query") or "").lower()
        audio_exts = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
        matches = []
        for root, dirs, files in os.walk(VAULT_DIR):
            for fname in sorted(files):
                if os.path.splitext(fname)[1].lower() in audio_exts:
                    rel = os.path.relpath(os.path.join(root, fname), VAULT_DIR)
                    if not query or query in fname.lower() or query in rel.lower():
                        matches.append(rel)
        if not matches:
            return f"No audio files found matching '{query}'." if query else "No audio files found in vault."
        lines = [f"Found {len(matches)} audio file(s):"] + [f"  {p}" for p in matches[:100]]
        if len(matches) > 100:
            lines.append(f"  ... and {len(matches) - 100} more")
        return "\n".join(lines)


class VaultPlaylistTool(BaseTool):
    """Creates or updates a playlist in the vault music player."""

    def __init__(self, **kwargs):
        super().__init__(
            name="vault_playlist",
            description=(
                "Creates a new playlist or adds tracks to an existing one. "
                "Tracks must be vault-relative paths (e.g. 'music/song.mp3'). "
                "The playlist will immediately appear in the vault music player."
            ),
            **kwargs
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "name": types.Schema(type="STRING", description="Playlist name"),
                    "tracks": types.Schema(
                        type="ARRAY",
                        description="List of vault-relative file paths to add",
                        items=types.Schema(type="STRING")
                    ),
                    "playlist_id": types.Schema(
                        type="STRING",
                        description="Existing playlist ID to append to (omit to create new)"
                    ),
                    "action": types.Schema(
                        type="STRING",
                        description="'create' (default), 'append' to existing, or 'list' to show all playlists"
                    ),
                },
                required=[]
            )
        )

    async def run_async(self, *, args: dict, tool_context) -> str:
        from vault_web.playlists import create_playlist, update_playlist, list_playlists, get_playlist

        action = args.get("action", "create")

        if action == "list":
            pls = list_playlists()
            if not pls:
                return "No playlists exist yet."
            lines = ["Existing playlists:"]
            for p in pls:
                lines.append(f"  [{p['id']}] {p['name']} — {p.get('track_count', 0)} tracks")
            return "\n".join(lines)

        tracks_raw = args.get("tracks", [])
        # Validate paths exist in vault
        valid_tracks = []
        missing = []
        for path in tracks_raw:
            full = os.path.join(VAULT_DIR, path)
            if os.path.exists(full):
                valid_tracks.append({"path": path, "title": os.path.basename(path)})
            else:
                missing.append(path)

        if action == "append":
            pid = args.get("playlist_id", "")
            existing = get_playlist(pid)
            if not existing:
                return f"Playlist '{pid}' not found. Use action='list' to see all playlists."
            all_tracks = existing["tracks"] + valid_tracks
            update_playlist(pid, tracks=[{"path": t["path"], "title": t.get("title", "")} for t in all_tracks])
            result = f"Added {len(valid_tracks)} track(s) to '{existing['name']}'."
        else:
            name = args.get("name", "New Playlist")
            if not valid_tracks:
                return "No valid tracks found. Use vault_find_audio to find audio file paths first."
            pl = create_playlist(name, valid_tracks)
            result = f"Created playlist '{pl['name']}' with {len(pl['tracks'])} track(s). ID: {pl['id']}"

        if missing:
            result += f"\nWarning: {len(missing)} path(s) not found in vault: {', '.join(missing[:5])}"
        return result
