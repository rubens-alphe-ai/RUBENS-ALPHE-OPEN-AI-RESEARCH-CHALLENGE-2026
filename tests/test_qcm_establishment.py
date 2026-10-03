"""The establishment dashboard reads a folder of exams and links one report per exam."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import qcm_establishment as qe  # noqa: E402
from test_qcm_report import class_csv  # noqa: E402


class EstablishmentTests(unittest.TestCase):
    def test_a_folder_becomes_a_dashboard_with_one_report_per_exam(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "in", Path(tmp) / "out"
            src.mkdir()
            (src / "Mathématiques__2nde_A__2026-12-08.csv").write_text(class_csv(3), encoding="utf-8")
            (src / "SVT__1re_B__2026-12-09.csv").write_text(class_csv(4), encoding="utf-8")
            summary = qe.build(src, out, "Lycée Test")
            self.assertEqual(summary["exams"], 2)
            self.assertTrue((out / "index.html").is_file())
            self.assertTrue((out / "rapport-Mathematiques__2nde_A__2026-12-08.html").is_file())
            self.assertIn("rapport-Mathematiques__2nde_A__2026-12-08.html", (out / "index.html").read_text(encoding="utf-8"))

    def test_badly_named_files_are_refused(self) -> None:
        with self.assertRaises(SystemExit):
            qe.describe(Path("examen.csv"))


if __name__ == "__main__":
    unittest.main()
