"""Tests for AI visitor note validation and the salted proof of reading."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_visitor_notes import check_note, salted_proof  # noqa: E402

PROOF_FILE = "experiments/PROP-EXP-MEM-001/TEST_PROMPT.md"


def make_note() -> dict:
    salt = "visitor-test-001"
    return {
        "note_version": "RA-PSI-VISITOR-NOTE-V1",
        "visited_at_utc": "2026-09-16T10:00:00Z",
        "visitor": {"name": "test agent", "model": "m", "provider": "p", "operator_consent": True},
        "capabilities": {"could_read_files": True, "could_execute_code": True, "could_write_to_repository": True},
        "what_i_read": ["docs/VISITORS.md"],
        "what_i_verified": [{"claim": "TEST_PROMPT exists", "method": "read it", "outcome": "confirmed"}],
        "note": "passing through",
        "proof_of_reading": {
            "salt": salt,
            "file": PROOF_FILE,
            "sha256_salted": salted_proof(salt, (ROOT / PROOF_FILE).read_bytes()),
        },
    }


class VisitorNoteTests(unittest.TestCase):
    def test_valid_note_with_valid_proof(self) -> None:
        errors, proof = check_note(make_note())
        self.assertEqual(errors, [])
        self.assertEqual(proof, "valid")

    def test_unsalted_file_hash_is_not_a_valid_proof(self) -> None:
        import hashlib

        note = make_note()
        note["proof_of_reading"]["sha256_salted"] = hashlib.sha256((ROOT / PROOF_FILE).read_bytes()).hexdigest()
        self.assertEqual(check_note(note)[1], "invalid")

    def test_changing_the_salt_invalidates_a_copied_proof(self) -> None:
        note = make_note()
        note["proof_of_reading"]["salt"] = "someone-else"
        self.assertEqual(check_note(note)[1], "invalid")

    def test_note_without_operator_consent_is_refused(self) -> None:
        note = make_note()
        note["visitor"]["operator_consent"] = False
        self.assertTrue(check_note(note)[0])

    def test_proof_cannot_point_outside_the_repository(self) -> None:
        note = make_note()
        note["proof_of_reading"]["file"] = "../../outside.txt"
        self.assertEqual(check_note(note)[1], "malformed")

    def test_note_without_proof_is_accepted_as_unproven(self) -> None:
        note = make_note()
        del note["proof_of_reading"]
        errors, proof = check_note(note)
        self.assertEqual(errors, [])
        self.assertEqual(proof, "absent")

    def test_unknown_verification_outcome_is_refused(self) -> None:
        note = copy.deepcopy(make_note())
        note["what_i_verified"][0]["outcome"] = "probably"
        self.assertTrue(check_note(note)[0])


if __name__ == "__main__":
    unittest.main()
