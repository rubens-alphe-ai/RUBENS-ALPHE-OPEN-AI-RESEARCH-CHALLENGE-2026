"""The seal is checkable from the repository without the repository holding it."""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "experiments" / "HOLDOUT-2026-09"
VAULT = Path("~/.ra-psi/holdout").expanduser()


class SealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.seal = json.loads((FOLDER / "SEAL.json").read_text(encoding="utf-8"))

    def test_the_repository_no_longer_holds_the_sealed_material(self) -> None:
        # This is the test that matters. Anything that can be grepped can leak,
        # and on 2026-09-19 two searches traversed this folder despite a README
        # asking them not to.
        for name in self.seal["files"]:
            self.assertFalse((FOLDER / name).exists(), name)

    def test_the_seal_names_the_commit_that_proves_it_predates_every_run(self) -> None:
        commit = self.seal["sealed_commit"]
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        found = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-t", commit],
                               capture_output=True, text=True)
        self.assertEqual(found.stdout.strip(), "commit")

    def test_every_sealed_file_still_hashes_to_what_was_recorded(self) -> None:
        # Skipped where the material is not present, so the seal stays checkable
        # on a machine that has it and the repository stays clean on one that
        # does not. The bytes are hashed, never read into a report.
        if not VAULT.is_dir():
            self.skipTest("sealed material is not on this machine, which is the normal case")
        for name, entry in self.seal["files"].items():
            path = VAULT / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"], name)
            self.assertEqual(path.stat().st_size, entry["bytes"], name)


if __name__ == "__main__":
    unittest.main()
