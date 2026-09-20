"""The portable auditor: it must never report unbacked as fine."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_claims as ac  # noqa: E402


def project(claims: list[dict], evidence: dict[str, str] | None = None) -> Path:
    folder = Path(tempfile.mkdtemp())
    for name, body in (evidence or {}).items():
        (folder / name).write_text(body, encoding="utf-8")
    path = folder / "claims.json"
    path.write_text(json.dumps({"root": ".", "claims": claims}), encoding="utf-8")
    return path


def echo(payload: object) -> str:
    """A recompute command that prints JSON, standing in for a real one."""
    return "%s -c \"import json;print(json.dumps(%r))\"" % (sys.executable, payload)


class StatusTests(unittest.TestCase):
    def test_a_claim_with_no_recompute_command_is_unverifiable_not_fine(self) -> None:
        path = project([{"id": "c1", "value": 5, "evidence": {}}])
        result = ac.audit(path, run=True, timeout=60)
        self.assertEqual(result["claims"][0]["status"], "UNVERIFIABLE")
        self.assertEqual(result["exit_code"], 2)

    def test_a_reproducing_claim_exits_clean(self) -> None:
        path = project([{"id": "c1", "value": {"delta": 5.5}, "recompute": echo({"delta": 5.5})}])
        result = ac.audit(path, run=True, timeout=60)
        self.assertEqual(result["claims"][0]["status"], "REPRODUCED")
        self.assertEqual(result["exit_code"], 0)

    def test_a_number_that_moved_is_named_with_its_path(self) -> None:
        path = project([{"id": "c1", "value": {"delta": 5.5, "pairs": 60},
                         "recompute": echo({"delta": 5.6, "pairs": 60})}])
        result = ac.audit(path, run=True, timeout=60)
        row = result["claims"][0]
        self.assertEqual(row["status"], "MISMATCH")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("delta", row["moved"][0])
        self.assertNotIn("pairs", " ".join(row["moved"]))

    def test_a_mismatch_outranks_an_unverifiable_claim(self) -> None:
        path = project([{"id": "a", "value": 1, "recompute": echo(2)},
                        {"id": "b", "value": 1}])
        self.assertEqual(ac.audit(path, run=True, timeout=60)["exit_code"], 1)

    def test_nothing_is_executed_without_the_run_flag(self) -> None:
        # The commands come from the audited project's own file. Running them is
        # a decision the operator makes after reading it.
        path = project([{"id": "c1", "value": 1, "recompute": "this-command-does-not-exist"}])
        result = ac.audit(path, run=False, timeout=60)
        self.assertEqual(result["claims"][0]["status"], "NOT_RUN")
        self.assertEqual(result["exit_code"], 2)


class EvidenceTests(unittest.TestCase):
    def test_evidence_that_changed_since_the_manifest_is_flagged(self) -> None:
        path = project([{"id": "c1", "value": 1, "recompute": echo(1),
                         "evidence": {"answers.json": "0" * 64}}],
                       evidence={"answers.json": "{}"})
        row = ac.audit(path, run=True, timeout=60)["claims"][0]
        self.assertEqual(row["evidence"], "EVIDENCE_CHANGED")
        self.assertEqual(row["status"], "EVIDENCE_CHANGED")

    def test_missing_evidence_is_reported_by_name(self) -> None:
        path = project([{"id": "c1", "value": 1, "recompute": echo(1), "evidence": {"gone.json": ""}}])
        row = ac.audit(path, run=True, timeout=60)["claims"][0]
        self.assertIn("missing: gone.json", row["evidence_problems"])

    def test_write_hashes_records_what_the_evidence_is_now(self) -> None:
        path = project([{"id": "c1", "value": 1, "evidence": {"answers.json": ""}}],
                       evidence={"answers.json": "{}"})
        ac.write_hashes(path)
        recorded = json.loads(path.read_text(encoding="utf-8"))["claims"][0]["evidence"]["answers.json"]
        self.assertEqual(len(recorded), 64)


class DiffTests(unittest.TestCase):
    def test_numbers_are_compared_as_numbers_not_as_text(self) -> None:
        self.assertEqual(ac.differences(5.0, 5), [])
        self.assertEqual(ac.differences({"a": 1.0000000001}, {"a": 1.0}), [])

    def test_a_pointer_reaches_one_number_inside_a_structure(self) -> None:
        self.assertEqual(ac.dig({"summary": {"ci": [1, 2]}}, "summary.ci.1"), 2)


class ExitCodeTests(unittest.TestCase):
    def test_a_checker_that_signals_a_finding_by_exiting_non_zero_is_still_read(self) -> None:
        # This project's own regression suite exits 1 when a number has moved.
        # An earlier version of recompute() called that unverifiable, which
        # silenced exactly the command most worth auditing.
        command = ("%s -c \"import json,sys;print(json.dumps({'delta': 5.5}));sys.exit(1)\""
                   % sys.executable)
        path = project([{"id": "c1", "value": {"delta": 5.5}, "recompute": command}])
        row = ac.audit(path, run=True, timeout=60)["claims"][0]
        self.assertEqual(row["status"], "REPRODUCED")

    def test_a_command_that_fails_without_printing_json_is_unverifiable(self) -> None:
        command = "%s -c \"import sys;sys.stderr.write('boom');sys.exit(3)\"" % sys.executable
        path = project([{"id": "c1", "value": 1, "recompute": command}])
        row = ac.audit(path, run=True, timeout=60)["claims"][0]
        self.assertEqual(row["status"], "UNVERIFIABLE")
        self.assertIn("exited 3", row["reason"])


if __name__ == "__main__":
    unittest.main()
