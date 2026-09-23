"""Cutting a panel down to its strongest respondents, and saying where the cut fell.

The restricted panel is where the September audit's whole finding lived, so the
risk here is not arithmetic. It is that the boundary gets drawn somewhere the
reader cannot see, or that a rounding turns a graded score into a ranking.

Nothing here touches the network.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import restrict_panel as rp  # noqa: E402


def write_table(path: Path, answers: dict[str, dict[str, object]],
                items: list[str] | None = None) -> Path:
    items = items or sorted({item for row in answers.values() for item in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial", "item", "correct"])
        writer.writeheader()
        for trial in answers:
            for item in items:
                if item in answers[trial]:
                    writer.writerow({"trial": trial, "item": item,
                                     "correct": answers[trial][item]})
    return path


class ReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def test_the_words_for_correctness_are_read_the_same_way_as_everywhere_else(self) -> None:
        path = self.dir / "words.csv"
        write_table(path, {"a": {"i1": "true", "i2": "no"},
                           "b": {"i1": "correct", "i2": "fail"}})
        by_trial, items = rp.read_table(path)
        self.assertEqual(items, ["i1", "i2"])
        self.assertEqual(by_trial, {"a": {"i1": 1, "i2": 0}, "b": {"i1": 1, "i2": 0}})

    def test_item_order_follows_the_file_rather_than_the_alphabet(self) -> None:
        path = self.dir / "order.csv"
        write_table(path, {"a": {"id10": 1, "id2": 0}}, items=["id10", "id2"])
        _by_trial, items = rp.read_table(path)
        self.assertEqual(items, ["id10", "id2"])

    def test_a_graded_score_is_refused_rather_than_rounded_into_a_ranking(self) -> None:
        # Rounding 0.6 to 1 does not merely blur one cell: it reorders the
        # respondents, and the panel is defined by that order.
        path = self.dir / "graded.csv"
        write_table(path, {"a": {"i1": 0.6}, "b": {"i1": 0.4}})
        with self.assertRaises(SystemExit) as raised:
            rp.read_table(path)
        self.assertIn("graded score", str(raised.exception))

    def test_a_table_missing_a_column_says_which_one(self) -> None:
        path = self.dir / "bad.csv"
        path.write_text("trial,item\na,i1\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            rp.read_table(path)
        self.assertIn("correct", str(raised.exception))

    def test_a_header_with_no_rows_is_refused(self) -> None:
        path = self.dir / "empty.csv"
        path.write_text("trial,item,correct\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            rp.read_table(path)


class RankingTests(unittest.TestCase):
    def test_trials_rank_by_total_correct_descending(self) -> None:
        by_trial = {"weak": {"i1": 0, "i2": 0}, "strong": {"i1": 1, "i2": 1},
                    "middling": {"i1": 1, "i2": 0}}
        self.assertEqual(rp.rank(by_trial, ["i1", "i2"]),
                         [("strong", 2), ("middling", 1), ("weak", 0)])

    def test_a_tie_is_broken_by_name_so_the_panel_is_reproducible(self) -> None:
        by_trial = {"zeta": {"i1": 1}, "alpha": {"i1": 1}}
        self.assertEqual([name for name, _ in rp.rank(by_trial, ["i1"])], ["alpha", "zeta"])

    def test_a_trial_short_of_an_item_is_ranked_on_what_it_answered(self) -> None:
        # Not on a zero it was never asked to earn, and not on a one either.
        by_trial = {"partial": {"i1": 1}, "whole": {"i1": 1, "i2": 0}}
        self.assertEqual(dict(rp.rank(by_trial, ["i1", "i2"])), {"partial": 1, "whole": 1})


class CutTests(unittest.TestCase):
    def test_the_gap_at_the_cut_is_reported(self) -> None:
        ranked = [("a", 9), ("b", 8), ("c", 8), ("d", 3), ("e", 1)]
        got = rp.cut(ranked, 3)
        self.assertEqual(got["kept"], ["a", "b", "c"])
        self.assertEqual(got["gap_at_the_cut"], 5)
        self.assertFalse(got["cut_falls_on_a_tie"])

    def test_a_boundary_that_fell_on_a_tie_says_so_and_names_the_tied(self) -> None:
        # The 3rd and 4th respondents are indistinguishable on this table; which
        # one made the panel was decided by their names, and a reader is owed
        # that fact rather than a tidy-looking top 3.
        ranked = [("a", 9), ("b", 9), ("c", 5), ("d", 5), ("e", 1)]
        got = rp.cut(ranked, 3)
        self.assertTrue(got["cut_falls_on_a_tie"])
        self.assertEqual(got["trials_tied_at_the_cut"], ["c", "d"])
        self.assertEqual(got["gap_at_the_cut"], 0)

    def test_a_panel_as_large_as_the_field_is_refused_as_no_restriction(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            rp.cut([("a", 2), ("b", 1), ("c", 0)], 3)
        self.assertIn("not a restriction", str(raised.exception))

    def test_a_panel_too_small_for_item_statistics_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            rp.cut([("a", 1), ("b", 0), ("c", 0), ("d", 0)], 2)
        with self.assertRaises(SystemExit):
            rp.cut([("a", 1), ("b", 0), ("c", 0), ("d", 0)], 0)


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.source = write_table(self.dir / "full.csv", {
            "m%02d" % n: {"i%d" % i: 1 if i <= n else 0 for i in range(1, 6)}
            for n in range(1, 8)
        })

    def run_script(self, *extra: str) -> dict:
        out = self.dir / "top.csv"
        manifest = self.dir / "top.panel.json"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "restrict_panel.py"),
             "--table", str(self.source), "--top", "3",
             "--out", str(out), "--manifest", str(manifest), *extra],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.out, self.manifest = out, manifest
        return json.loads(manifest.read_text(encoding="utf-8"))

    def test_only_the_strongest_trials_survive_and_their_answers_are_unchanged(self) -> None:
        record = self.run_script()
        with self.out.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(sorted({row["trial"] for row in rows}), ["m05", "m06", "m07"])
        self.assertEqual(len(rows), 15)
        with self.source.open(encoding="utf-8") as handle:
            original = {(r["trial"], r["item"]): r["correct"] for r in csv.DictReader(handle)}
        for row in rows:
            self.assertEqual(row["correct"], original[(row["trial"], row["item"])])
        self.assertEqual(record["trials_in_full_field"], 7)
        self.assertEqual(record["trials_kept"], 3)

    def test_the_manifest_hashes_the_table_it_came_from(self) -> None:
        import hashlib
        record = self.run_script()
        self.assertEqual(record["source_table_sha256"],
                         hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(record["record_version"], "RA-PSI-PANEL-V1")

    def test_the_rule_that_picked_the_panel_is_written_down(self) -> None:
        record = self.run_script()
        self.assertIn("total items correct", record["rule"])
        self.assertEqual(record["scores"]["m07"], 5)

    def test_require_complete_refuses_a_trial_that_skipped_an_item(self) -> None:
        write_table(self.dir / "full.csv", {
            "m1": {"i1": 1, "i2": 1}, "m2": {"i1": 1, "i2": 0},
            "m3": {"i1": 0, "i2": 0}, "m4": {"i1": 0},
        })
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "restrict_panel.py"),
             "--table", str(self.dir / "full.csv"), "--top", "3",
             "--out", str(self.dir / "t.csv"), "--require-complete"],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("m4", proc.stderr)


if __name__ == "__main__":
    unittest.main()
