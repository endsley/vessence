#!/usr/bin/env python3
"""Nightly cron: evolve CODE_MAP_KEYWORDS from daily conversations.

Reads today's user messages from the SQLite ledger, identifies code-related
messages, extracts new candidate keywords, and appends any that appear in
2+ code-related messages to the CODE_MAP_KEYWORDS tuple in jane_proxy.py.

Schedule: 10 2 * * * (2:10 AM daily)
"""

import datetime
import logging
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
VESSENCE_HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VESSENCE_HOME))

LEDGER_DB = Path(os.environ.get(
    "VAULT_HOME",
    Path.home() / "ambient" / "vault",
)) / "conversation_history_ledger.db"

JANE_PROXY_PATH = VESSENCE_HOME / "jane_web" / "jane_proxy.py"
CONTEXT_BUILDER_PATH = VESSENCE_HOME / "jane" / "context_builder.py"
CODE_MAP_PATH = VESSENCE_HOME / "configs" / "CODE_MAP_CORE.md"

PYTHON_BIN = "/home/chieh/google-adk-env/adk-venv/bin/python"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [evolve_keywords] %(message)s",
)
logger = logging.getLogger("evolve_keywords")

# ---------------------------------------------------------------------------
# Stopwords — common English words that should never become keywords
# ---------------------------------------------------------------------------
STOPWORDS = frozenset({
    # Articles / determiners
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each",
    # Pronouns
    "i", "me", "you", "he", "she", "it", "we", "they", "them", "us",
    "who", "what", "which", "whom", "whose",
    # Prepositions
    "in", "on", "at", "to", "for", "with", "from", "by", "about", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "under", "over", "up", "down", "out", "off", "of",
    # Conjunctions
    "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
    # Verbs (common)
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing", "done",
    "will", "would", "shall", "should", "may", "might", "must", "can", "could",
    "get", "got", "go", "going", "went", "gone", "come", "came",
    "make", "made", "take", "took", "give", "gave", "say", "said",
    "know", "knew", "think", "thought", "see", "saw", "want", "wanted",
    "use", "used", "find", "found", "tell", "told", "ask", "asked",
    "work", "seem", "feel", "try", "leave", "call", "need", "let",
    "keep", "put", "show", "mean", "set", "run", "read", "look",
    "like", "just", "also", "still", "right", "here", "there",
    # Adjectives / adverbs
    "good", "new", "first", "last", "long", "great", "little", "own",
    "other", "old", "big", "high", "small", "large", "next", "early",
    "young", "important", "few", "public", "bad", "same", "able",
    "very", "really", "too", "quite", "well", "much", "more", "most",
    "only", "then", "now", "when", "how", "where", "why",
    "not", "all", "many", "if", "than", "even", "because", "way",
    # Filler / conversational
    "ok", "okay", "yes", "no", "yeah", "nah", "sure", "thanks", "thank",
    "please", "hey", "hi", "hello", "bye", "hmm", "oh", "ah", "um",
    "thing", "things", "stuff", "something", "anything", "nothing",
    "everything", "one", "two", "three", "four", "five",
    # Time
    "today", "tomorrow", "yesterday", "morning", "night", "day", "week",
    "month", "year", "time", "hour", "minute", "second",
    # Misc
    "don't", "doesn't", "didn't", "won't", "wouldn't", "can't", "couldn't",
    "shouldn't", "isn't", "aren't", "wasn't", "weren't", "haven't", "hasn't",
    "hadn't", "actually", "probably", "maybe", "already", "always", "never",
    "sometimes", "often", "again", "back", "around", "together",
    "enough", "kind", "sort", "lot", "bit", "part", "point",
    "going", "pretty", "really", "quite",
})


# ---------------------------------------------------------------------------
# Step 1: Read today's user messages from the ledger
# ---------------------------------------------------------------------------
def get_todays_user_messages() -> list[str]:
    """Return user messages from today (UTC)."""
    if not LEDGER_DB.exists():
        logger.warning("Ledger DB not found: %s", LEDGER_DB)
        return []

    today = datetime.date.today().isoformat()  # YYYY-MM-DD
    conn = sqlite3.connect(str(LEDGER_DB))
    try:
        rows = conn.execute(
            "SELECT content FROM turns WHERE role = 'user' AND date(timestamp) = ?",
            (today,),
        ).fetchall()
    finally:
        conn.close()

    messages = [row[0] for row in rows if row[0] and row[0].strip()]
    logger.info("Found %d user messages for %s", len(messages), today)
    return messages


# ---------------------------------------------------------------------------
# Step 2: Load current keyword lists
# ---------------------------------------------------------------------------
def parse_tuple_from_file(filepath: Path, var_name: str) -> tuple[str, ...]:
    """Parse a Python tuple assigned to var_name from a source file."""
    source = filepath.read_text()
    # Match: VAR_NAME = (\n  ...\n)
    pattern = rf'{var_name}\s*=\s*\((.*?)\)'
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        logger.warning("Could not parse %s from %s", var_name, filepath)
        return ()
    inner = match.group(1)
    # Extract all quoted strings
    return tuple(re.findall(r'"([^"]*)"', inner))


def load_all_keywords() -> set[str]:
    """Load all existing keywords from proxy and context_builder."""
    kw = set()
    kw.update(parse_tuple_from_file(JANE_PROXY_PATH, "CODE_MAP_KEYWORDS"))
    kw.update(parse_tuple_from_file(CONTEXT_BUILDER_PATH, "TASK_KEYWORDS"))
    kw.update(parse_tuple_from_file(CONTEXT_BUILDER_PATH, "AI_CODING_KEYWORDS"))
    logger.info("Loaded %d existing keywords", len(kw))
    return kw


# ---------------------------------------------------------------------------
# Step 3: Load file/function names from CODE_MAP_CORE.md
# ---------------------------------------------------------------------------
def load_code_map_names() -> set[str]:
    """Extract file names and function/class names from the code map."""
    names: set[str] = set()
    if not CODE_MAP_PATH.exists():
        logger.warning("Code map not found: %s", CODE_MAP_PATH)
        return names

    text = CODE_MAP_PATH.read_text()

    # File names from "### path/to/file.py (N lines)" headers
    for m in re.finditer(r'###\s+(\S+\.(?:py|html|kt|js|ts))', text):
        full_path = m.group(1)
        filename = full_path.rsplit("/", 1)[-1]
        names.add(filename.lower())
        # Also add without extension for matching
        stem = filename.rsplit(".", 1)[0]
        names.add(stem.lower())

    # Function/class names from "  name() → L123" or "  class Name → L123"
    for m in re.finditer(r'(\w+)\(\)\s*→\s*L\d+', text):
        name = m.group(1)
        if len(name) > 2:  # Skip very short names
            names.add(name.lower())
    for m in re.finditer(r'class\s+(\w+)', text):
        name = m.group(1)
        if len(name) > 2:
            names.add(name.lower())

    logger.info("Loaded %d file/function/class names from code map", len(names))
    return names


# ---------------------------------------------------------------------------
# Step 4: Identify code-related messages
# ---------------------------------------------------------------------------
def is_code_related(message: str, keywords: set[str], code_map_names: set[str]) -> bool:
    """Check if a message is code-related based on keywords and code map names."""
    lowered = message.lower()
    # Check existing keywords
    if any(kw in lowered for kw in keywords):
        return True
    # Check code map file/function names
    if any(name in lowered for name in code_map_names if len(name) > 3):
        return True
    return False


# ---------------------------------------------------------------------------
# Step 5: Extract candidate keywords from code-related messages
# ---------------------------------------------------------------------------
def extract_candidates(
    messages: list[str],
    existing_keywords: set[str],
    code_map_names: set[str],
) -> list[str]:
    """Extract new keyword candidates appearing in 2+ code-related messages."""
    code_messages = [
        m for m in messages
        if is_code_related(m, existing_keywords, code_map_names)
    ]
    logger.info("%d of %d messages identified as code-related",
                len(code_messages), len(messages))

    if len(code_messages) < 2:
        return []

    # Build the set of all known words to exclude
    known_lower = {kw.lower() for kw in existing_keywords}
    known_lower.update(STOPWORDS)

    # Count words across code-related messages
    word_counter: Counter[str] = Counter()
    for msg in code_messages:
        # Tokenize: alphanumeric words and underscored identifiers
        words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', msg.lower()))
        for w in words:
            if (len(w) >= 3
                    and w not in known_lower
                    and not w.isdigit()
                    and "_" not in w[:1]):  # skip leading underscore (private names)
                word_counter[w] += 1

    # Only keep words in 2+ code-related messages
    candidates = [
        word for word, count in word_counter.most_common()
        if count >= 2
    ]

    logger.info("Found %d candidate keywords (2+ occurrences)", len(candidates))
    return candidates


# ---------------------------------------------------------------------------
# Step 6: Update CODE_MAP_KEYWORDS in jane_proxy.py
# ---------------------------------------------------------------------------
def update_keywords_file(new_keywords: list[str]) -> bool:
    """Append new keywords to the CODE_MAP_KEYWORDS tuple in jane_proxy.py.

    Returns True if the file was modified.
    """
    if not new_keywords:
        return False

    source = JANE_PROXY_PATH.read_text()

    # Find the closing paren of CODE_MAP_KEYWORDS
    pattern = r'(CODE_MAP_KEYWORDS\s*=\s*\(.*?)(^\))'
    match = re.search(pattern, source, re.DOTALL | re.MULTILINE)
    if not match:
        logger.error("Could not locate CODE_MAP_KEYWORDS tuple in %s", JANE_PROXY_PATH)
        return False

    before_close = match.group(1)
    # Build the new keyword lines
    keyword_lines = []
    for kw in new_keywords:
        keyword_lines.append(f'    "{kw}",')

    insert_block = (
        "    # Auto-evolved from daily conversations\n"
        + "\n".join(keyword_lines)
        + "\n"
    )

    new_source = source[:match.end(1)] + insert_block + source[match.start(2):]
    JANE_PROXY_PATH.write_text(new_source)
    logger.info("Updated %s with %d new keywords: %s",
                JANE_PROXY_PATH, len(new_keywords), new_keywords)
    return True


# ---------------------------------------------------------------------------
# Step 7: Restart jane-web if file was modified
# ---------------------------------------------------------------------------
def restart_jane_web():
    """Restart jane-web.service to pick up new keywords."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "jane-web.service"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("jane-web.service restarted successfully")
        else:
            logger.warning("jane-web restart returned %d: %s",
                           result.returncode, result.stderr.strip())
    except Exception as e:
        logger.error("Failed to restart jane-web: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("=== Evolve Code Map Keywords — %s ===", datetime.date.today())

    # 1. Get today's user messages
    messages = get_todays_user_messages()
    if not messages:
        logger.info("No user messages today. Nothing to do.")
        return

    # 2. Load existing keywords
    existing_keywords = load_all_keywords()

    # 3. Load code map names
    code_map_names = load_code_map_names()

    # 4-5. Extract candidate keywords
    candidates = extract_candidates(messages, existing_keywords, code_map_names)
    if not candidates:
        logger.info("No new keywords to add.")
        return

    # Cap at 10 new keywords per day to avoid noise
    candidates = candidates[:10]
    logger.info("Adding keywords: %s", candidates)

    # 6. Update the file
    modified = update_keywords_file(candidates)

    # 7. Restart if modified
    if modified:
        restart_jane_web()

    logger.info("Done.")


if __name__ == "__main__":
    main()
