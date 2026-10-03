"""The outreach record has to hold the comments the verdict will be judged on."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import track_outreach as tracker  # noqa: E402


class CommentTests(unittest.TestCase):
    def test_replies_nested_under_a_comment_are_kept(self) -> None:
        # Counting 13 and storing 3 was the top level only.
        tree = [{"content": "a", "replies": [{"content": "b", "replies": [{"content": "c"}]}]},
                {"content": "d"}]
        self.assertEqual([c["content"] for c in tracker.flatten(tree)], ["a", "b", "c", "d"])

    def test_an_author_is_stored_as_a_name_not_a_profile(self) -> None:
        self.assertEqual(tracker.author_name({"author": {"name": "vina", "karma": 1}}), "vina")
        self.assertEqual(tracker.author_name({"agent": {"name": "zhaoxuan"}}), "zhaoxuan")
        self.assertEqual(tracker.author_name({"author": "plain"}), "plain")
        self.assertIsNone(tracker.author_name({}))


if __name__ == "__main__":
    unittest.main()
