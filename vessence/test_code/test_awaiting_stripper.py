"""Unit tests for the streaming AWAITING marker stripper.

Covers the various ways Stage 3 can stream a marker at the end of its
response — single chunk, split chunks, marker starting mid-chunk,
false-alarm `[[` prefix, etc.
"""
from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "/home/chieh/ambient/vessence")

from jane_web.jane_v2.pipeline import _AwaitingDeltaStripper  # noqa: E402


class StripperSingleChunkTest(unittest.TestCase):
    def _run(self, chunks: list[str]) -> str:
        s = _AwaitingDeltaStripper()
        out = []
        for c in chunks:
            out.append(s.feed(c))
        out.append(s.flush())
        return "".join(out)

    def test_no_marker_passes_through(self) -> None:
        out = self._run(["Hello there, how are you?"])
        self.assertEqual(out, "Hello there, how are you?")

    def test_single_chunk_marker_stripped(self) -> None:
        out = self._run(["Which pasta? [[AWAITING:pasta_choice]]"])
        self.assertEqual(out, "Which pasta? ")

    def test_marker_at_very_start(self) -> None:
        out = self._run(["[[AWAITING:only_marker]]"])
        self.assertEqual(out, "")

    def test_trailing_space_preserved_before_marker(self) -> None:
        out = self._run(["Yes. [[AWAITING:confirm]]"])
        self.assertEqual(out, "Yes. ")


class StripperSplitChunkTest(unittest.TestCase):
    def _run(self, chunks: list[str]) -> str:
        s = _AwaitingDeltaStripper()
        out = []
        for c in chunks:
            out.append(s.feed(c))
        out.append(s.flush())
        return "".join(out)

    def test_split_between_letters(self) -> None:
        out = self._run([
            "The answer is forty two. ",
            "[[AWAIT",
            "ING:confirm_math]]",
        ])
        self.assertEqual(out, "The answer is forty two. ")

    def test_split_after_brackets(self) -> None:
        out = self._run([
            "hello world ",
            "[[",
            "AWAITING:topic]]",
        ])
        self.assertEqual(out, "hello world ")

    def test_single_bracket_is_harmless(self) -> None:
        # A lone `[[` that never becomes a marker should still emit.
        out = self._run([
            "see section ",
            "[[notes]]",
            " for details",
        ])
        self.assertEqual(out, "see section [[notes]] for details")

    def test_partial_marker_prefix_but_not_actual(self) -> None:
        out = self._run([
            "draft text ",
            "[[AWA",
            "RDS:best_of_year]]",
        ])
        self.assertEqual(out, "draft text [[AWARDS:best_of_year]]")

    def test_many_small_chunks(self) -> None:
        text = "Please tell me. [[AWAITING:pasta]]"
        chunks = [text[i:i+1] for i in range(len(text))]
        out = self._run(chunks)
        self.assertEqual(out, "Please tell me. ")


class StripperEdgeCaseTest(unittest.TestCase):
    def _run(self, chunks: list[str]) -> str:
        s = _AwaitingDeltaStripper()
        out = []
        for c in chunks:
            out.append(s.feed(c))
        out.append(s.flush())
        return "".join(out)

    def test_empty_chunks(self) -> None:
        out = self._run(["", "", ""])
        self.assertEqual(out, "")

    def test_only_flush_no_feed(self) -> None:
        s = _AwaitingDeltaStripper()
        self.assertEqual(s.flush(), "")

    def test_content_after_marker_is_dropped(self) -> None:
        # In practice the marker is always the final thing, but verify
        # that trailing content after the marker is still suppressed.
        out = self._run([
            "answer ",
            "[[AWAITING:topic]]",
            " should_not_appear",
        ])
        self.assertEqual(out, "answer ")

    def test_suppress_state_persists(self) -> None:
        # Once suppressed, no further feed yields output.
        s = _AwaitingDeltaStripper()
        self.assertEqual(s.feed("hi [[AWAITING:x]]"), "hi ")
        self.assertEqual(s.feed("ignored"), "")
        self.assertEqual(s.feed("also ignored"), "")
        self.assertEqual(s.flush(), "")

    def test_ending_with_ambiguous_tail_buffers(self) -> None:
        # Stream ends with a `[[` that never resolves — should flush it.
        out = self._run(["hello ["])
        self.assertEqual(out, "hello [")

    def test_ending_with_double_bracket_no_marker(self) -> None:
        out = self._run(["hello [["])
        self.assertEqual(out, "hello [[")


if __name__ == "__main__":
    unittest.main(verbosity=2)
