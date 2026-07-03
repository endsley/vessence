"""Helper functions for Jane web vault file routes."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import StreamingResponse

MIME_TO_SUBDIR = {
    "image": "images",
    "audio": "audio",
    "video": "video",
}

FILE_TYPE_EXTENSIONS = {
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "document": {".pdf", ".doc", ".docx", ".txt", ".md"},
}


def route_subdir(mime: str) -> str:
    if mime == "application/pdf":
        return "pdf"
    top = mime.split("/")[0]
    return MIME_TO_SUBDIR.get(top, "documents")


def paginate_listing(listing: dict, offset: int, limit: int) -> dict:
    """Apply optional offset/limit pagination to a directory listing.
    When limit <= 0, return the full listing (backwards compatible).
    Pagination applies to files only; folders are always returned in full.
    """
    if limit <= 0:
        return listing
    if "error" in listing:
        return listing
    files = listing.get("files", [])
    total_files = len(files)
    paginated_files = files[offset:offset + limit]
    listing["files"] = paginated_files
    listing["total_files"] = total_files
    listing["offset"] = offset
    listing["limit"] = limit
    return listing


def range_response(path: Path, mime: str, range_header: str):
    size = path.stat().st_size
    start, end = 0, size - 1
    try:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0]) if ranges[0] else 0
        end = int(ranges[1]) if ranges[1] else size - 1
    except Exception:
        pass
    end = min(end, size - 1)
    length = end - start + 1

    def iter_file():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(iter_file(), status_code=206, media_type=mime, headers={
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    })


def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for ftype, exts in FILE_TYPE_EXTENSIONS.items():
        if ext in exts:
            return ftype
    return "other"
