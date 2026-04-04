"""files.py — Vault file browsing, metadata, thumbnails."""
import os
import sys
import mimetypes
import datetime
import re
from pathlib import Path
from PIL import Image
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    VAULT_DIR,
    VECTOR_DB_FILE_INDEX,
    CHROMA_COLLECTION_FILE_INDEX,
)

try:
    from .database import get_db
except ImportError:
    from database import get_db

THUMBNAIL_SIZE = (180, 180)

ICON_MAP = {
    # Images
    "jpg": "🖼️", "jpeg": "🖼️", "png": "🖼️", "gif": "🖼️", "webp": "🖼️", "svg": "🖼️",
    # Video
    "mp4": "🎬", "mov": "🎬", "avi": "🎬", "mkv": "🎬", "webm": "🎬",
    # Audio
    "mp3": "🎵", "wav": "🎵", "flac": "🎵", "ogg": "🎵", "m4a": "🎵", "aac": "🎵",
    # PDF
    "pdf": "📄",
    # Documents
    "doc": "📝", "docx": "📝", "txt": "📝", "md": "📝", "rtf": "📝",
    # Data
    "csv": "📊", "xlsx": "📊", "xls": "📊", "json": "📊",
    # Archives
    "zip": "🗜️", "tar": "🗜️", "gz": "🗜️",
}

IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm", "m4g"}
AUDIO_EXTS = {"mp3", "wav", "flac", "ogg", "m4a", "aac"}
TEXT_EXTS  = {
    "txt", "md", "markdown", "rst",
    "py", "js", "ts", "jsx", "tsx", "sh", "bash",
    "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "env",
    "csv", "log", "sql", "xml", "html", "css",
}
TEXT_SIZE_LIMIT = 512 * 1024  # 512 KB — larger files offered as download only


def is_text(filename: str) -> bool:
    return ext(filename) in TEXT_EXTS


def safe_vault_path(rel_path: str) -> Path:
    """Resolve a relative path safely within VAULT_DIR."""
    vault = Path(VAULT_DIR).resolve()
    target = (vault / rel_path.lstrip("/")).resolve()
    if not str(target).startswith(str(vault)):
        raise ValueError("Path traversal detected")
    return target


def ext(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def file_icon(filename: str) -> str:
    return ICON_MAP.get(ext(filename), "📁")


def is_image(filename: str) -> bool:
    return ext(filename) in IMAGE_EXTS


def is_video(filename: str) -> bool:
    return ext(filename) in VIDEO_EXTS


def is_audio(filename: str) -> bool:
    return ext(filename) in AUDIO_EXTS

def is_text(filename: str) -> bool:
    return ext(filename) in TEXT_EXTS


def get_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def make_descriptive_filename(original_name: str, description: str) -> str:
    """Derive a readable filename stem from a user-provided description."""
    source = (description or "").strip().lower()
    if not source:
        return Path(original_name or "upload").name

    ext_name = Path(original_name or "upload").suffix.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", source).strip("-")
    words = [part for part in stem.split("-") if part]
    stem = "-".join(words[:8])[:72].strip("-")
    if not stem:
        stem = "image"
    return f"{stem}{ext_name}"


def build_file_index_document(rel_path: str, description: str, mime_type: str) -> str:
    filename = Path(rel_path).name
    full_path = safe_vault_path(rel_path)
    details = (description or "").strip() or f"File '{filename}' stored in the vault."
    return f"Vault file: '{filename}' at path {full_path}. {details} File type: {mime_type}."


def upsert_file_index_entry(rel_path: str, description: str, mime_type: str, updated_by: str = "web_ui") -> bool:
    """Persist a vault file record into the dedicated file-index collection."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=VECTOR_DB_FILE_INDEX)
        coll = client.get_or_create_collection(
            CHROMA_COLLECTION_FILE_INDEX,
            metadata={"hnsw:space": "cosine"},
        )
        filename = Path(rel_path).name
        doc_id = f"vault_file_{rel_path.replace('/', '_').replace('.', '_')}"
        coll.upsert(
            ids=[doc_id],
            documents=[build_file_index_document(rel_path, description, mime_type)],
            metadatas=[{
                "source": "vault",
                "topic": "file_index",
                "memory_type": "file_index",
                "path": rel_path,
                "filename": filename,
                "mime_type": mime_type,
                "updated_by": updated_by,
            }],
        )
        return True
    except Exception:
        return False


def list_directory(rel_path: str = "") -> dict:
    """List files and folders at a vault path."""
    try:
        target = safe_vault_path(rel_path)
    except ValueError:
        return {"error": "Invalid path"}

    if not target.exists() or not target.is_dir():
        return {"error": "Not found"}

    folders = []
    files = []

    for item in sorted(target.iterdir(), key=lambda x: x.name.lower()):
        if item.name.startswith(".") or item.name.endswith(".db"):
            continue
        if item.is_dir():
            file_count = sum(1 for f in item.rglob("*") if f.is_file() and not f.name.startswith("."))
            folders.append({
                "name": item.name,
                "path": str(item.relative_to(VAULT_DIR)),
                "type": "folder",
                "file_count": file_count,
            })
        else:
            stat = item.stat()
            file_ext = ext(item.name)
            entry = {
                "name": item.name,
                "path": str(item.relative_to(VAULT_DIR)),
                "type": "file",
                "ext": file_ext,
                "icon": file_icon(item.name),
                "size": stat.st_size,
                "size_human": _human_size(stat.st_size),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_image": is_image(item.name),
                "is_video": is_video(item.name),
                "is_audio": is_audio(item.name),
                "is_pdf": file_ext == "pdf",
                "is_text": is_text(item.name),
                "mime": get_mime(item.name),
            }
            files.append(entry)

    return {
        "path": rel_path,
        "folders": folders,
        "files": files,
    }


def get_file_metadata(rel_path: str) -> dict:
    """Get file info + ChromaDB description."""
    try:
        target = safe_vault_path(rel_path)
    except ValueError:
        return {"error": "Invalid path"}

    if not target.exists() or not target.is_file():
        return {"error": "Not found"}

    stat = target.stat()
    filename = target.name
    file_ext = ext(filename)

    meta = {
        "name": filename,
        "path": rel_path,
        "ext": file_ext,
        "icon": file_icon(filename),
        "size": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_image": is_image(filename),
        "is_video": is_video(filename),
        "is_audio": is_audio(filename),
        "is_pdf": file_ext == "pdf",
        "is_text": is_text(filename),
        "mime": get_mime(filename),
        "description": "",
        "chroma_meta": {},
    }

    # Fetch from ChromaDB
    try:
        import chromadb
        client = chromadb.PersistentClient(path=VECTOR_DB_FILE_INDEX)
        coll = client.get_or_create_collection(CHROMA_COLLECTION_FILE_INDEX)
        results = coll.query(
            query_texts=[f"file {filename} vault {rel_path}"],
            n_results=3,
            where={"source": "vault"} if False else None,  # broad search
        )
        if results["documents"] and results["documents"][0]:
            # Find the best match by path
            for i, doc in enumerate(results["documents"][0]):
                m = results["metadatas"][0][i] if results["metadatas"] else {}
                if rel_path in doc or filename in doc:
                    meta["description"] = doc
                    meta["chroma_meta"] = m
                    break
    except Exception:
        pass

    return meta


def update_description(rel_path: str, description: str):
    """Update file description in ChromaDB."""
    try:
        if not upsert_file_index_entry(rel_path, description, get_mime(rel_path), updated_by="web_ui"):
            return False
        # Log change to file_changes for polling
        with get_db() as conn:
            conn.execute("INSERT INTO file_changes DEFAULT VALUES")
        return True
    except Exception as e:
        return False


def get_last_change_timestamp() -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT changed_at FROM file_changes ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["changed_at"] if row else ""


def generate_thumbnail(rel_path: str) -> bytes | None:
    """Generate a JPEG thumbnail for an image."""
    try:
        target = safe_vault_path(rel_path)
        if not target.exists() or not is_image(target.name):
            return None
        with Image.open(target) as img:
            img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
    except Exception:
        return None


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
