"""Pure Gmail message payload helpers."""

from __future__ import annotations

import base64
import re


COMMON_HEADERS = ("from", "to", "cc", "bcc", "subject", "date")


def parse_headers(headers: list[dict]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header in headers:
        name = header.get("name", "").lower()
        if name in COMMON_HEADERS:
            result[name] = header.get("value", "")
    return result


def decode_body_data(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def strip_html_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def extract_plain_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return decode_body_data(data)

    for part in payload.get("parts", []):
        text = extract_plain_body(part)
        if text:
            return text

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return strip_html_tags(decode_body_data(data))

    return ""


def extract_attachments(payload: dict) -> list[dict]:
    attachments = []
    for part in payload.get("parts", []):
        filename = part.get("filename")
        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId", ""),
            })
        attachments.extend(extract_attachments(part))
    return attachments
