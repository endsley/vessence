"""Static file indexers used by generate_code_map.py."""
from __future__ import annotations

import ast
import re


SKIP_DIRS = {"__pycache__", "node_modules", "omniparser", ".git", "test_code", "venv", "build", ".gradle"}
SKIP_FILES = {"__init__.py"}

MAX_ENTRIES_PRIORITY = 50
MAX_ENTRIES_SECONDARY = 20
ROUTE_METHODS = {"get", "post", "put", "delete", "patch"}


def count_lines(filepath: str) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return 0


def route_entry_from_decorator(decorator: ast.expr, lineno: int) -> str:
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return ""
    method = decorator.func.attr
    if method not in ROUTE_METHODS:
        return ""
    if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
        return ""
    return f"  {method.upper()} {decorator.args[0].value} → L{lineno}"


def index_python_file(filepath: str) -> list[str]:
    """Extract functions, classes, decorators, and constants from a Python file."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            source = handle.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, Exception):
        return entries

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            entries.append(f"  class {node.name} → L{node.lineno}-{end}")
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item_end = getattr(item, "end_lineno", item.lineno)
                    entries.append(f"    {item.name}() → L{item.lineno}-{item_end}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            route = ""
            for dec in node.decorator_list:
                route = route_entry_from_decorator(dec, node.lineno)
                if route:
                    break
            if route:
                entries.append(route)
            else:
                entries.append(f"  {node.name}() → L{node.lineno}-{end}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 2:
                    entries.append(f"  {target.id} = ... → L{node.lineno}")

    return entries


def index_html_file(filepath: str) -> list[str]:
    """Extract Alpine.js methods and event handlers from HTML."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except Exception:
        return entries

    for i, line in enumerate(lines, 1):
        m = re.match(r'\s{8,}(async\s+)?(\w+)\s*\(.*\)\s*\{', line)
        if m and m.group(2) not in ("if", "for", "while", "switch", "catch", "else", "function", "return"):
            name = m.group(2)
            prefix = "async " if m.group(1) else ""
            entries.append(f"  {prefix}{name}() → L{i}")

        m = re.search(r"event\.type\s*===?\s*['\"](\w+)['\"]", line)
        if m:
            entries.append(f"  event.type === '{m.group(1)}' → L{i}")

    seen = set()
    unique = []
    for entry in entries:
        if entry not in seen:
            seen.add(entry)
            unique.append(entry)
    return unique


def index_kotlin_file(filepath: str) -> list[str]:
    """Extract classes, objects, functions, and @Composable functions from a Kotlin file."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except Exception:
        return entries

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or not stripped:
            continue

        m = re.match(r'^\s*((?:data|sealed|abstract|open|private|internal)\s+)*(class|object|interface)\s+(\w+)', line)
        if m:
            kind = m.group(2)
            name = m.group(3)
            entries.append(f"  {kind} {name} → L{i}")
            continue

        if stripped == "@Composable":
            if i < len(lines):
                next_line = lines[i].strip()
                m = re.match(r'(?:(?:private|internal)\s+)?fun\s+(\w+)', next_line)
                if m:
                    entries.append(f"  @Composable {m.group(1)}() → L{i + 1}")
                    lines[i] = "\n"
            continue

        m = re.match(r'^(\s*)((?:override|suspend|private|internal|protected|open)\s+)*fun\s+(\w+)', line)
        if m:
            indent = len(m.group(1))
            name = m.group(3)
            modifiers = (m.group(2) or "").strip()
            prefix = ""
            if "suspend" in modifiers:
                prefix = "suspend "
            if "override" in modifiers:
                prefix = "override "
            if indent >= 4:
                entries.append(f"    {prefix}{name}() → L{i}")
            else:
                entries.append(f"  {prefix}{name}() → L{i}")
            continue

        m = re.match(r'^\s+(?:const\s+)?val\s+([A-Z_]{3,})\s*[=:]', line)
        if m:
            entries.append(f"    {m.group(1)} → L{i}")

    return entries


def index_file(fpath: str, functions_only: bool = False) -> list[str]:
    """Index a single file."""
    if fpath.endswith(".py"):
        entries = index_python_file(fpath)
        if functions_only:
            entries = [e for e in entries if "()" in e or e.strip().startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH "))]
        return entries
    if fpath.endswith(".html"):
        return index_html_file(fpath)
    if fpath.endswith(".kt"):
        entries = index_kotlin_file(fpath)
        if functions_only:
            entries = [e for e in entries if "()" in e or "class " in e or "object " in e or "interface " in e]
        return entries
    return []


def should_skip(fpath: str, fname: str) -> bool:
    if fname in SKIP_FILES:
        return True
    if any(skip in fpath for skip in SKIP_DIRS):
        return True
    return False


def cap_entries(entries: list[str]) -> list[str]:
    """Apply priority-file entry cap."""
    if len(entries) <= MAX_ENTRIES_PRIORITY:
        return entries
    routes = [e for e in entries if any(m in e for m in ("GET ", "POST ", "PUT ", "DELETE ", "PATCH "))]
    funcs = [e for e in entries if "()" in e]
    classes = [e for e in entries if "class " in e]
    consts = [e for e in entries if "= ..." in e]
    result = classes + routes + funcs
    remaining = MAX_ENTRIES_PRIORITY - len(result)
    if remaining > 0:
        result.extend(consts[:remaining])
    return result[:MAX_ENTRIES_PRIORITY]
