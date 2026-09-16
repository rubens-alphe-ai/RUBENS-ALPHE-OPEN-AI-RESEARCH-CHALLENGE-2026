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


from validate_visitor_notes import assess  # noqa: E402


class EvidenceTierTests(unittest.TestCase):
    """A note is graded by what it proves, never by the identity it claims."""

    def test_valid_proof_is_read_proven_whatever_the_claimed_identity(self) -> None:
        note = make_note()
        note["visitor"]["model"] = "a self-declared superintelligence"
        tier, _ = assess(note, check_note(note)[1])
        self.assertEqual(tier, "read_proven")

    def test_impressive_identity_without_proof_is_claim_only(self) -> None:
        note = make_note()
        del note["proof_of_reading"]
        note["visitor"]["model"] = "the most capable system in existence"
        tier, flags = assess(note, check_note(note)[1])
        self.assertEqual(tier, "claim_only")
        self.assertIn("claims code execution but demonstrated none", flags)

    def test_denying_execution_while_computing_a_proof_is_flagged(self) -> None:
        note = make_note()
        note["capabilities"]["could_execute_code"] = False
        _, flags = assess(note, check_note(note)[1])
        self.assertTrue(any("yet produced a valid computed proof" in flag for flag in flags))

    def test_declared_delegation_must_name_its_chain(self) -> None:
        note = make_note()
        note["note_version"] = "RA-PSI-VISITOR-NOTE-V2"
        note["delegation"] = {"written_by_delegate": True}
        errors, proof = check_note(note)
        self.assertEqual(errors, [])
        self.assertIn("declares delegation without naming the chain", assess(note, proof)[1])

    def test_malformed_delegation_is_refused(self) -> None:
        note = make_note()
        note["delegation"] = {"written_by_delegate": "maybe"}
        self.assertTrue(check_note(note)[0])


class MaintainerIsolationTests(unittest.TestCase):
    """Outsider content never reaches the model that proposes code edits."""

    def test_visitor_notes_are_never_editable(self) -> None:
        from maintainer_agent import editable

        self.assertIsNotNone(editable("visitors/2026-09-16-x.json", "visitor_notes_valid"))

    def test_visitor_notes_are_never_fed_to_the_model(self) -> None:
        import tempfile

        from maintainer_agent import implicated_files

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "visitors").mkdir()
            (project / "visitors" / "note.json").write_text("{}", encoding="utf-8")
            (project / "scripts").mkdir()
            (project / "scripts" / "tool.py").write_text("x = 1\n", encoding="utf-8")
            found = implicated_files(project, "failure in visitors/note.json and scripts/tool.py")
        self.assertEqual(found, ["scripts/tool.py"])
