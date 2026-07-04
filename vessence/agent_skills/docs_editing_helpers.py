"""Pure helpers for Google Docs text extraction and TODO edits."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|\-|\*|•)\s+")
NUMBERED_ITEM_RE = re.compile(r"^\s*(\d+)[.)]\s+")


@dataclass(frozen=True)
class TodoReplacementPlan:
    old_text: str
    new_text: str
    success_message: str
    failure_message: str


@dataclass(frozen=True)
class TodoAddSectionScan:
    found_section: bool
    insert_after_line: str | None
    numbered_insert_line: str | None
    last_item_num: int


@dataclass(frozen=True)
class TodoRemoveItemScan:
    line: str
    item_body: str


def extract_text(body: dict[str, Any]) -> str:
    """Walk the Docs body JSON and extract plain text."""
    parts = []
    for elem in body.get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            tr = pe.get("textRun")
            if tr:
                parts.append(tr.get("content", ""))
    return "".join(parts)


def find_end_of_section(text: str, section_name: str) -> int | None:
    """Find the character index at the end of a section."""
    lines = text.split("\n")
    in_section = False
    char_offset = 0
    last_content_end = None

    for line in lines:
        line_len = len(line) + 1
        stripped = line.strip()
        if stripped.lower() == section_name.lower():
            in_section = True
            char_offset += line_len
            continue
        if in_section:
            if stripped and not LIST_ITEM_RE.match(line):
                if last_content_end is not None:
                    return last_content_end
            if stripped:
                last_content_end = char_offset + line_len
        char_offset += line_len

    return last_content_end or char_offset


def build_insert_text_request(index: int, text: str) -> dict[str, Any]:
    return {
        "insertText": {
            "location": {"index": index},
            "text": text,
        }
    }


def build_replace_all_text_request(old_text: str, new_text: str) -> dict[str, Any]:
    return {
        "replaceAllText": {
            "containsText": {
                "text": old_text,
                "matchCase": True,
            },
            "replaceText": new_text,
        }
    }


def plan_todo_add_item(
    full_text: str,
    item_text: str,
    category: str,
) -> TodoReplacementPlan | None:
    scan = scan_todo_add_section(full_text, category)
    if not scan.found_section or scan.insert_after_line is None:
        return None

    insert_after_line = scan.insert_after_line
    if scan.numbered_insert_line is not None:
        insert_after_line = scan.numbered_insert_line
        new_item = f"\n{scan.last_item_num + 1}. {item_text}"
        confirmation = f"Added item #{scan.last_item_num + 1} to {category}: {item_text}"
    else:
        new_item = f"\n{item_text}"
        confirmation = f"Added item to {category}: {item_text}"

    return TodoReplacementPlan(
        old_text=insert_after_line,
        new_text=insert_after_line + new_item,
        success_message=confirmation,
        failure_message=f"Failed to add item to {category}.",
    )


def scan_todo_add_section(full_text: str, category: str) -> TodoAddSectionScan:
    lines = full_text.split("\n")
    in_section = False
    found_section = False
    last_item_num = 0
    numbered_insert_line = None
    insert_after_line = None
    section_has_items = False

    for line in lines:
        stripped = line.strip()
        if stripped.lower() == category.lower():
            in_section = True
            found_section = True
            insert_after_line = line
            continue
        if in_section:
            if not stripped:
                if section_has_items:
                    break
                continue
            m = NUMBERED_ITEM_RE.match(line)
            if m:
                last_item_num = int(m.group(1))
                numbered_insert_line = line
            insert_after_line = line
            section_has_items = True

    return TodoAddSectionScan(
        found_section=found_section,
        insert_after_line=insert_after_line,
        numbered_insert_line=numbered_insert_line,
        last_item_num=last_item_num,
    )


def plan_todo_remove_item(
    full_text: str,
    item_text: str,
    category: str | None = None,
) -> TodoReplacementPlan | None:
    scan = scan_todo_remove_item(full_text, item_text, category)
    if scan is None:
        return None
    return TodoReplacementPlan(
        old_text=scan.line + "\n",
        new_text="",
        success_message=f"Removed: {scan.item_body}",
        failure_message="Found the item but failed to delete it.",
    )


def scan_todo_remove_item(
    full_text: str,
    item_text: str,
    category: str | None = None,
) -> TodoRemoveItemScan | None:
    target = item_text.lower().strip()
    in_section = category is None
    section_has_items = False

    for line in full_text.split("\n"):
        stripped = line.strip()
        if category is not None and stripped.lower() == category.lower():
            in_section = True
            continue
        if not in_section:
            continue
        if not stripped:
            if category is not None and section_has_items:
                break
            continue
        section_has_items = True
        item_body = LIST_ITEM_RE.sub("", line).strip()
        if target in item_body.lower():
            return TodoRemoveItemScan(line=line, item_body=item_body)

    return None


def todo_category_exists(full_text: str, category_name: str) -> bool:
    target = category_name.strip().lower()
    return any(line.strip().lower() == target for line in full_text.split("\n"))


def build_todo_category_section(category_name: str) -> str:
    return f"\n\n{category_name}\n1. Nothing\n"
