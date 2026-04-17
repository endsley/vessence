"""Tests for TODO list fetcher + Stage 2 handler.

Covers:
  - Parser handles BOM, CRLF, blank lines, numbered markers.
  - Fetcher safely rejects login-wall HTML.
  - Handler asks "which category?" on first turn, reads back on follow-up.
  - Category matching: alias, numeric, ordinal, name-contains, excluded.
  - Ambient project goals / "Jane" category excluded → escalate to Stage 3.
  - Missing cache falls back gracefully.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/home/chieh/ambient/vessence")

from agent_skills import fetch_todo_list  # noqa: E402
from jane_web.jane_v2.classes.todo_list import handler as todo_handler  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_DOC = (
    "\ufeffDo it Immediately\r\n"
    "1. Deal with some important email.\r\n\r\n\r\n"
    "For my students\r\n"
    "1. Write the recommendation letter\r\n\r\n\r\n"
    "For our Home\r\n"
    "1. Put the TV from kathia's room to the gym.\r\n"
    "2. Clean downstairs\r\n\r\n\r\n"
    "For the clinic\r\n"
    "1. Curtain rods at kathia's clinic\r\n"
    "2. The wooden block for the door at the clinic\r\n\r\n\r\n"
    "Jane\r\n"
    "1. Set it up so users use claude code to run Jane\r\n"
    "2. Let the user have an easy web/android jane\r\n"
)

LOGIN_WALL_HTML = (
    "<!DOCTYPE html><html><head><title>Sign in - Google Accounts"
    "</title></head><body>Please sign in.</body></html>"
)


def _sample_cache() -> dict:
    cats = fetch_todo_list.parse_categories(SAMPLE_DOC)
    return {
        "fetched_at": "2026-04-16T20:00:00Z",
        "doc_id": "test",
        "source_url": "test://doc",
        "categories": cats,
        "raw_text": SAMPLE_DOC,
    }


# ── Parser tests ──────────────────────────────────────────────────────────────


class ParseCategoriesTest(unittest.TestCase):
    def test_parses_five_categories(self) -> None:
        cats = fetch_todo_list.parse_categories(SAMPLE_DOC)
        self.assertEqual(len(cats), 5)

    def test_strips_bom_from_first_header(self) -> None:
        cats = fetch_todo_list.parse_categories(SAMPLE_DOC)
        self.assertFalse(cats[0]["name"].startswith("\ufeff"))
        self.assertEqual(cats[0]["name"], "Do it Immediately")

    def test_items_extracted_without_markers(self) -> None:
        cats = fetch_todo_list.parse_categories(SAMPLE_DOC)
        home = next(c for c in cats if c["name"] == "For our Home")
        self.assertEqual(len(home["items"]), 2)
        self.assertEqual(home["items"][0], "Put the TV from kathia's room to the gym.")
        self.assertFalse(home["items"][0].startswith("1."))

    def test_handles_dash_markers(self) -> None:
        text = "Groceries\n- milk\n- eggs\n"
        cats = fetch_todo_list.parse_categories(text)
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]["items"], ["milk", "eggs"])

    def test_skips_prose_without_list(self) -> None:
        text = "Here's my notes about today.\n\nShopping\n1. milk\n"
        cats = fetch_todo_list.parse_categories(text)
        # "Here's my notes..." has no list items below it, so it's not
        # promoted to a category.
        self.assertEqual([c["name"] for c in cats], ["Shopping"])


# ── Fetcher safety tests ──────────────────────────────────────────────────────


class FetchSafetyTest(unittest.TestCase):
    def test_rejects_login_wall_html(self) -> None:
        class FakeResp:
            status = 200
            def read(self): return LOGIN_WALL_HTML.encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_todo_list.fetch_doc_text("x")
            self.assertIn("HTML login page", str(ctx.exception))

    def test_rejects_empty_body(self) -> None:
        class FakeResp:
            status = 200
            def read(self): return b""
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            with self.assertRaises(RuntimeError):
                fetch_todo_list.fetch_doc_text("x")

    def test_round_trip(self) -> None:
        class FakeResp:
            status = 200
            def read(self): return SAMPLE_DOC.encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            text = fetch_todo_list.fetch_doc_text("test-doc")
        cats = fetch_todo_list.parse_categories(text)
        self.assertEqual(len(cats), 5)


# ── Handler category matching ────────────────────────────────────────────────


class MatchCategoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cats = _sample_cache()["categories"]

    def test_alias_urgent(self) -> None:
        m = todo_handler._match_category("urgent", self.cats)
        self.assertEqual(m["name"], "Do it Immediately")

    def test_alias_immediately(self) -> None:
        m = todo_handler._match_category("do it immediately", self.cats)
        self.assertEqual(m["name"], "Do it Immediately")

    def test_alias_clinic(self) -> None:
        m = todo_handler._match_category("clinic", self.cats)
        self.assertEqual(m["name"], "For the clinic")

    def test_alias_home(self) -> None:
        m = todo_handler._match_category("tell me about home", self.cats)
        self.assertEqual(m["name"], "For our Home")

    def test_students(self) -> None:
        m = todo_handler._match_category("students", self.cats)
        self.assertEqual(m["name"], "For my students")

    def test_ordinal_third(self) -> None:
        # Among visible categories: [Do it Immediately, students, Home, clinic]
        # So "third" → Home.
        m = todo_handler._match_category("third", self.cats)
        self.assertEqual(m["name"], "For our Home")

    def test_numeric_fallback(self) -> None:
        m = todo_handler._match_category("number 1", self.cats)
        self.assertEqual(m["name"], "Do it Immediately")

    def test_no_match_returns_none(self) -> None:
        m = todo_handler._match_category("purple elephants", self.cats)
        self.assertIsNone(m)


class ExclusionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cats = _sample_cache()["categories"]

    def test_ambient_project_not_matched(self) -> None:
        for q in (
            "ambient project",
            "what's my ambient project goal",
            "jane",
            "jane project",
        ):
            with self.subTest(q=q):
                self.assertIsNone(todo_handler._match_category(q, self.cats))

    def test_visible_categories_drops_jane(self) -> None:
        visible = todo_handler._visible_categories(self.cats)
        names = [c["name"] for c in visible]
        self.assertNotIn("Jane", names)
        self.assertIn("Do it Immediately", names)

    def test_opener_lists_four_not_five(self) -> None:
        text = todo_handler._speak_category_list(self.cats)
        self.assertIn("4 categories", text)
        self.assertNotIn("Jane", text.lower())


# ── Handler flow: opener + resume ────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


class HandlerFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = _sample_cache()
        # Point the handler at an ephemeral cache file.
        fd, path = tempfile.mkstemp(suffix="_todo.json")
        os.close(fd)
        self.cache_path = Path(path)
        self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")
        self._prev_cache_env = os.environ.get("TODO_CACHE_PATH")
        os.environ["TODO_CACHE_PATH"] = str(self.cache_path)
        # Monkey-patch the module-level _CACHE_PATH (already computed from env).
        self._prev_module_path = todo_handler._CACHE_PATH
        todo_handler._CACHE_PATH = self.cache_path

    def tearDown(self) -> None:
        todo_handler._CACHE_PATH = self._prev_module_path
        if self._prev_cache_env is None:
            os.environ.pop("TODO_CACHE_PATH", None)
        else:
            os.environ["TODO_CACHE_PATH"] = self._prev_cache_env
        self.cache_path.unlink(missing_ok=True)

    def test_opener_asks_which_category(self) -> None:
        out = _run(todo_handler.handle("what's on my todo list"))
        self.assertIsNotNone(out)
        self.assertIn("categories", out["text"].lower())
        self.assertIn("which one", out["text"].lower())
        pending = out["structured"]["pending_action"]
        self.assertEqual(pending["type"], "STAGE2_FOLLOWUP")
        self.assertEqual(pending["handler_class"], "todo list")
        self.assertEqual(pending["awaiting"], "category")

    def test_direct_category_skips_question(self) -> None:
        out = _run(todo_handler.handle("what's on my clinic list"))
        self.assertIsNotNone(out)
        # Direct hit — should read items, no pending.
        self.assertIn("clinic", out["text"].lower())
        self.assertNotIn("pending_action", out["structured"])

    def test_resume_with_category(self) -> None:
        pending = {"awaiting": "category"}
        out = _run(todo_handler.handle("clinic", pending=pending))
        self.assertIsNotNone(out)
        self.assertIn("clinic", out["text"].lower())
        # Items spoken.
        self.assertIn("curtain rods", out["text"].lower())

    def test_resume_unmatched_reasks(self) -> None:
        pending = {"awaiting": "category"}
        out = _run(todo_handler.handle("purple elephants", pending=pending))
        self.assertIsNotNone(out)
        self.assertIn("didn't catch", out["text"].lower())
        self.assertIn(
            "pending_action", out["structured"],
            "should keep pending_action alive for another retry",
        )

    def test_resume_pivot_abandons(self) -> None:
        pending = {"awaiting": "category"}
        out = _run(todo_handler.handle(
            "what's the weather today", pending=pending,
        ))
        self.assertEqual(out, {"abandon_pending": True})


class MissingCacheTest(unittest.TestCase):
    def test_no_cache_returns_friendly_message(self) -> None:
        with patch.object(todo_handler, "_load_cache", return_value=None):
            out = _run(todo_handler.handle("what's on my todo list"))
            self.assertIsNotNone(out)
            self.assertIn("cached copy", out["text"].lower())


class ClassifierMetadataTest(unittest.TestCase):
    """Metadata should tell Stage 1 that ambient-project prompts go to
    Stage 3, not to this handler."""

    def test_ambient_contrast_exemplars_exist(self) -> None:
        from jane_web.jane_v2.classes.todo_list.metadata import METADATA
        ambient_rows = [
            (p, label) for (p, label) in METADATA["few_shot"]
            if "ambient" in p.lower()
        ]
        self.assertGreaterEqual(len(ambient_rows), 2)
        for _, label in ambient_rows:
            self.assertNotIn("todo list", label,
                             "Ambient prompts must NOT route to todo list")

    def test_class_registers(self) -> None:
        from jane_web.jane_v2.classes import get_registry
        reg = get_registry(refresh=True)
        self.assertIn("todo list", reg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
