"""Every file an experiment manifest hashes must still hash to that value.

MEM-002's states were hashed on Windows with CRLF line endings and published
with LF, so the public copy silently disagreed with its own manifest. Nothing
failed; a reader checking provenance would have found a broken chain. This
test makes that failure loud.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def recorded_pairs(node, found: list) -> list:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.endswith("_path") and isinstance(value, str):
                digest = node.get(key[: -len("_path")] + "_sha256")
                if isinstance(digest, str):
                    found.append((value, digest))
            recorded_pairs(value, found)
    elif isinstance(node, list):
        for item in node:
            recorded_pairs(item, found)
    return found


class PublishedHashTests(unittest.TestCase):
    def test_manifest_hashes_match_files(self) -> None:
        checked = 0
        for manifest in sorted(ROOT.glob("experiments/*/results/experiment-manifest.json")):
            for relative, digest in recorded_pairs(json.loads(manifest.read_text(encoding="utf-8")), []):
                path = ROOT / relative
                if not path.is_file():
                    continue  # private or not yet published
                with self.subTest(manifest=manifest.parent.parent.name, file=relative):
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
