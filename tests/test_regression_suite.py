"""What the regression suite must notice, and what it must refuse to call agreement.

Most of these tests build a small experiment in a temporary directory rather
than leaning on the real results. Pinning behaviour to the real files would
make the suite pass for as long as nobody touched them and say nothing about
what it detects; a fixture can be given a number that moved on purpose.

Two tests do run over the real repository. One asserts that every experiment
whose verdict is recomputable still recomputes. The other records, by name, the
published numbers that do *not* follow from the stored answers, so that a
finding cannot quietly become normal. Those numbers are not corrected here:
editing a stored result to make a check pass is the one thing this suite exists
to prevent.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402
import regression_suite as rs  # noqa: E402

# MEM-007's decision.json does not follow from MEM-007's stored answers. The
# answers give 46 pairs better, 10 equal and an interval of +3.71 to +7.23; the
# decision file says 45, 11 and +3.70 to +7.24. Every file involved still
# matches its hash in SHA256SUMS.json, so nothing was altered after
# publication: the decision was written from a reading that differs from the
# one archived beside it. RESULT.md and the registry both say 46, so the prose
# is right and the machine-readable verdict is the stale artefact. It is listed
# here, not repaired, because repairing it would mean editing a published
# result to make a test go green.
KNOWN_UNREPRODUCIBLE = {"PROP-EXP-MEM-007": ["decision.json"]}

# Verdicts whose supporting answers were never stored. They cannot be shown to
# be wrong; they cannot be shown to be right either, which is the whole claim.
KNOWN_UNVERIFIABLE = {
    # A second reading of MEM-006 by the NVIDIA Kimi reader. Its answers are not
    # in the repository, so only the summary survives.
    "PROP-EXP-MEM-006": ["decision-kimi-reader.json"],
    # MEM-009 stores one grade per merged chain but neither the reader answers
    # nor an answer key, so its recovery figures can be re-read and not regraded.
    "PROP-EXP-MEM-009": ["clinic-summary", "clinic-summary-w300", "observatory-summary",
                         "observatory-summary-w300", "vineyard-summary", "vineyard-summary-w300"],
}

NOT_STATED = "the text does not say"


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def quiz(facts: int = 4, absent: int = 2) -> dict:
    """A quiz of the shape the real ones have: five options, the last one absent."""
    questions = []
    for index in range(facts):
        questions.append({"id": "Q%02d" % (index + 1), "kind": "fact",
                          "question": "fact %d?" % index, "correct": "right %d" % index,
                          "distractors": ["wrong %d.%d" % (index, other) for other in range(3)]})
    for index in range(absent):
        questions.append({"id": "A%02d" % (index + 1), "kind": "absent",
                          "question": "absent %d?" % index,
                          "distractors": ["invented %d.%d" % (index, other) for other in range(4)]})
    return {"quiz_version": "fixture-1", "not_stated_option": NOT_STATED, "questions": questions}


def answers_for(key: dict[str, str], rendered: list[dict], correct: int) -> dict[str, str]:
    """Answer the first `correct` fact questions right, the rest "does not say"."""
    given, right = {}, 0
    for item in rendered:
        if item["kind"] == "absent":
            given[item["id"]] = hq.LETTERS[-1]
        elif right < correct:
            given[item["id"]] = key[item["id"]]
            right += 1
        else:
            given[item["id"]] = hq.LETTERS[-1]
    return given


class Fixture:
    """A repository with one experiment in it, built from scratch in a temp dir."""

    def __init__(self, directory: Path, experiment_id: str = "PROP-EXP-MEM-900",
                 status: str = "REJECTED") -> None:
        self.root = directory
        self.experiment = directory / "experiments" / experiment_id
        (self.experiment / "results").mkdir(parents=True, exist_ok=True)
        write(directory / "experiments" / "registry.json",
              {"registry_version": "RA-PSI-REGISTRY-V1",
               "experiments": [{"experiment_id": experiment_id, "status": status}]})

    def paired_quiz(self, scores: list[tuple[int, int]]) -> dict:
        """One pair per (baseline correct, structured correct); returns the true verdict."""
        write(self.experiment / "QUIZ.json", quiz())
        write(self.experiment / "evaluation_policy.json",
              {"quiz": {"file": "QUIZ.json", "keep_min_delta_pp": 5, "invention_margin": 5}})
        rendered, key = hq.render_quiz(quiz(), self.experiment.name + ":fixture-1")
        write(self.experiment / "results" / "quiz" / "answer-key.json", {"key": key})
        pairs = []
        for index, (baseline, structured) in enumerate(scores):
            pair_id = "pair-%03d" % index
            graded = {"pair_id": pair_id}
            for condition, correct in (("baseline", baseline), ("structured", structured)):
                given = answers_for(key, rendered, correct)
                graded[condition] = hq.grade(given, key, rendered)
                write(self.experiment / "results" / "quiz" / ("%s-%s.json" % (condition, pair_id)),
                      {"trial_id": "%s-%s" % (condition, pair_id), "pair_id": pair_id,
                       "condition": condition, "answers": given, "grade": graded[condition]})
            pairs.append(graded)
        verdict = hq.decide(pairs, {"keep_min_delta_pp": 5, "invention_margin": 5})
        write(self.experiment / "results" / "decision.json",
              {**verdict, "experiment_id": self.experiment.name,
               "rule": {"keep_min_delta_pp": 5, "invention_margin": 5}})
        return verdict

    def chain(self, document: str = "fixture", arms: tuple[str, ...] = ("summary", "checklist"),
              repeats: int = 3) -> dict:
        """One chain per arm and repeat, read at hop 1; returns the true table."""
        rendered, key = hq.render_quiz(quiz(), "%s.md:fixture-1" % document)
        directory = self.experiment / "results" / document
        write(directory / "answer-key.json", {"key": key, "rendered": rendered})
        records = []
        for arm_index, arm in enumerate(arms):
            for repeat in range(1, repeats + 1):
                given = answers_for(key, rendered, 1 + arm_index + (repeat % 2))
                record = {"strategy": arm, "repeat": repeat, "read_at": [1], "word_limit": 150,
                          "chain": [{"hop": 1, "text": "note", "words_kept": 100, "trimmed": False}],
                          "grades": {"1": {"answers": given, "problems": [],
                                           **hq.grade(given, key, rendered)}}}
                write(directory / ("%s-%02d.json" % (arm, repeat)), record)
                records.append(record)
        table = {"1": hb.summarise(records, 1, control=arms[0])}
        write(directory / "report.json", {"meta": {"document": document, "failed_runs": 0},
                                          "by_hop": table})
        return table


class DifferenceTests(unittest.TestCase):
    def test_a_gap_inside_the_stated_tolerance_is_not_reported_as_a_difference(self) -> None:
        self.assertEqual(rs.differences({"delta": 1.0}, {"delta": 1.0 + rs.TOLERANCE / 2}), [])

    def test_a_gap_above_the_stated_tolerance_is_reported_with_the_tolerance_named(self) -> None:
        found = rs.differences({"delta": 1.0}, {"delta": 1.1})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["field"], "delta")
        self.assertIn("tolerance", found[0]["why"])

    def test_numbers_are_compared_as_numbers_and_not_as_formatted_strings(self) -> None:
        # 0.1 + 0.2 prints as 0.30000000000000004 and must still count as 0.3.
        self.assertEqual(rs.differences(0.1 + 0.2, 0.3, "sum"), [])
        self.assertNotEqual(rs.differences("0.3", 0.3, "sum"), [])

    def test_a_field_missing_from_either_side_is_named_rather_than_ignored(self) -> None:
        found = rs.differences({"a": 1}, {"a": 1, "b": 2})
        self.assertEqual([item["field"] for item in found], ["b"])
        found = rs.differences({"a": 1, "b": 2}, {"a": 1})
        self.assertEqual([item["field"] for item in found], ["b"])

    def test_a_deep_field_is_named_by_its_full_path(self) -> None:
        found = rs.differences({"by_hop": {"3": {"checklist": {"facts_kept_pct": 90.0}}}},
                               {"by_hop": {"3": {"checklist": {"facts_kept_pct": 80.0}}}})
        self.assertEqual(found[0]["field"], "by_hop.3.checklist.facts_kept_pct")


class PairedQuizTests(unittest.TestCase):
    def test_a_paired_verdict_that_follows_from_its_answers_is_reported_as_reproduced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.REPRODUCED)
            self.assertEqual(report["exit_code"], rs.EXIT_OK)
            self.assertGreater(row["checks"], 0)

    def test_a_published_delta_that_does_not_follow_from_the_answers_is_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["summary"]["mean_paired_delta_pp"] += 4.0
            write(path, published)
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.MISMATCH)
            self.assertEqual(report["exit_code"], rs.EXIT_MISMATCH)
            fields = [item["field"] for item in row["units"][0]["differences"]]
            self.assertIn("summary.mean_paired_delta_pp", fields)

    def test_a_published_verdict_letter_that_the_answers_do_not_support_is_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["decision"] = "PROVISIONAL_KEEP"
            write(path, published)
            report = rs.run(Path(directory))
            self.assertEqual(report["experiments"][0]["status"], rs.MISMATCH)

    def test_a_stored_grade_that_disagrees_with_its_own_answers_is_caught(self) -> None:
        # The aggregate could still come out right; the record would be lying
        # about what the reader answered, and that is what is being checked.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "quiz" / "baseline-pair-000.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["grade"]["fact_correct"] += 1
            write(path, record)
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.MISMATCH)
            fields = [item["field"] for item in row["units"][0]["differences"]]
            self.assertIn("baseline-pair-000.json.grade.fact_correct", fields)

    def test_an_answer_key_that_no_longer_follows_from_the_quiz_file_is_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "quiz" / "answer-key.json"
            stored = json.loads(path.read_text(encoding="utf-8"))
            stored["key"]["Q01"] = "B" if stored["key"]["Q01"] != "B" else "C"
            write(path, stored)
            report = rs.run(Path(directory))
            self.assertEqual(report["experiments"][0]["status"], rs.MISMATCH)

    def test_a_decision_with_no_answers_beside_it_is_unverifiable_and_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            published = json.loads((fixture.experiment / "results" / "decision.json").read_text(encoding="utf-8"))
            write(fixture.experiment / "results" / "decision-other-reader.json", published)
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.UNVERIFIABLE)
            orphan = [item for item in row["units"] if item["unit"] == "decision-other-reader.json"][0]
            self.assertEqual(orphan["status"], rs.UNVERIFIABLE)
            self.assertTrue(orphan["notes"])
            self.assertIsNotNone(orphan["effect"]["published"])

    def test_an_unverifiable_verdict_exits_non_zero_but_distinctly_from_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            published = json.loads((fixture.experiment / "results" / "decision.json").read_text(encoding="utf-8"))
            write(fixture.experiment / "results" / "decision-other-reader.json", published)
            report = rs.run(Path(directory))
            self.assertEqual(report["exit_code"], rs.EXIT_UNVERIFIABLE)
            self.assertNotEqual(rs.EXIT_UNVERIFIABLE, rs.EXIT_MISMATCH)
            self.assertNotEqual(rs.EXIT_UNVERIFIABLE, rs.EXIT_OK)

    def test_a_mismatch_outranks_an_unverifiable_in_the_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            write(fixture.experiment / "results" / "decision-other-reader.json", published)
            published["summary"]["pairs"] = 99
            write(path, published)
            report = rs.run(Path(directory))
            self.assertEqual(report["exit_code"], rs.EXIT_MISMATCH)

    def test_the_effect_is_reported_on_both_sides_so_the_reader_sees_what_moved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            truth = fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["summary"]["mean_paired_delta_pp"] = 99.0
            write(path, published)
            effect = rs.run(Path(directory))["experiments"][0]["units"][0]["effect"]
            self.assertAlmostEqual(effect["recomputed"]["mean_paired_delta_pp"],
                                   truth["summary"]["mean_paired_delta_pp"])
            self.assertEqual(effect["published"]["mean_paired_delta_pp"], 99.0)


class ChainTests(unittest.TestCase):
    def test_a_chain_table_that_follows_from_the_stored_grades_is_reported_as_reproduced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain()
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["shape"], "chain")
            self.assertEqual(row["status"], rs.REPRODUCED)
            self.assertEqual(report["exit_code"], rs.EXIT_OK)

    def test_a_chain_number_that_moved_is_named_with_its_document_and_its_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain(document="vineyard")
            path = fixture.experiment / "results" / "vineyard" / "report.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["by_hop"]["1"]["checklist"]["facts_kept_pct"] += 10.0
            write(path, published)
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.MISMATCH)
            moved = [item for item in row["units"] if item["unit"] == "vineyard"][0]
            self.assertEqual(moved["status"], rs.MISMATCH)
            self.assertIn("by_hop.1.checklist.facts_kept_pct",
                          [item["field"] for item in moved["differences"]])

    def test_each_document_of_a_chain_is_checked_on_its_own(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain(document="clinic")
            fixture.chain(document="observatory")
            row = rs.run(Path(directory))["experiments"][0]
            self.assertEqual(sorted(item["unit"] for item in row["units"]), ["clinic", "observatory"])

    def test_the_control_arm_is_read_from_the_published_table_not_assumed(self) -> None:
        # handoff_bench controls on "summary", anchored_chain on "bare". Assuming
        # either one would silently recompute a different experiment.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            table = fixture.chain(document="anchored", arms=("bare", "anchored"))
            self.assertEqual(rs.control_arm(table), "bare")
            row = rs.run(Path(directory))["experiments"][0]
            self.assertEqual(row["units"][0]["control"], "bare")
            self.assertEqual(row["status"], rs.REPRODUCED)

    def test_a_chain_grade_edited_away_from_its_answers_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain(document="clinic")
            path = fixture.experiment / "results" / "clinic" / "checklist-01.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["grades"]["1"]["fact_accuracy"] = 1.0
            write(path, record)
            row = rs.run(Path(directory))["experiments"][0]
            self.assertEqual(row["status"], rs.MISMATCH)
            self.assertIn("checklist-01.json.grades.1.fact_accuracy",
                          [item["field"] for item in row["units"][0]["differences"]])

    def test_a_report_without_raw_answers_is_unverifiable_rather_than_reproduced(self) -> None:
        # This is MEM-009's shape: grades were filed, the answers behind them
        # were not, so the table can be re-read but never regraded.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain(document="clinic")
            for path in (fixture.experiment / "results" / "clinic").glob("*-0*.json"):
                record = json.loads(path.read_text(encoding="utf-8"))
                for grade in record["grades"].values():
                    grade.pop("answers", None)
                record.pop("grades")
                write(path, record)
            report = rs.run(Path(directory))
            self.assertEqual(report["experiments"][0]["status"], rs.UNVERIFIABLE)
            self.assertEqual(report["exit_code"], rs.EXIT_UNVERIFIABLE)

    def test_a_failed_run_that_the_report_never_counted_is_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.chain(document="clinic")
            write(fixture.experiment / "results" / "clinic" / "checklist-09.failed.json",
                  {"strategy": "checklist", "repeat": 9, "error": "no answer"})
            row = rs.run(Path(directory))["experiments"][0]
            self.assertEqual(row["status"], rs.MISMATCH)
            self.assertIn("meta.failed_runs", [item["field"] for item in row["units"][0]["differences"]])


class WalkTests(unittest.TestCase):
    def test_an_experiment_without_a_verdict_is_listed_rather_than_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Fixture(Path(directory), status="OPEN")
            report = rs.run(Path(directory))
            row = report["experiments"][0]
            self.assertEqual(row["status"], rs.NO_VERDICT)
            self.assertEqual(report["exit_code"], rs.EXIT_OK)
            self.assertTrue(row["note"])

    def test_a_verdict_with_no_recomputable_result_at_all_is_unverifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Fixture(Path(directory), status="REJECTED")
            report = rs.run(Path(directory))
            self.assertEqual(report["experiments"][0]["status"], rs.UNVERIFIABLE)
            self.assertEqual(report["exit_code"], rs.EXIT_UNVERIFIABLE)

    def test_the_rendered_report_states_the_tolerance_it_compared_with(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            text = rs.render(rs.run(Path(directory)))
            self.assertIn("%g" % rs.TOLERANCE, text)

    def test_the_rendered_report_spells_out_which_number_moved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["summary"]["sd_delta_pp"] = 42.0
            write(path, published)
            text = rs.render(rs.run(Path(directory)))
            self.assertIn("PROP-EXP-MEM-900", text)
            self.assertIn("summary.sd_delta_pp", text)
            self.assertIn("42.0", text)

    def test_the_command_line_entry_point_exits_non_zero_when_a_number_moved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.paired_quiz([(1, 3), (2, 4), (1, 2), (2, 2)])
            path = fixture.experiment / "results" / "decision.json"
            published = json.loads(path.read_text(encoding="utf-8"))
            published["summary"]["pairs"] = 99
            write(path, published)
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                code = rs.main(["--root", str(directory), "--json"])
            self.assertEqual(code, rs.EXIT_MISMATCH)
            self.assertEqual(json.loads(captured.getvalue())["exit_code"], rs.EXIT_MISMATCH)


class RealRepositoryTests(unittest.TestCase):
    """The promise, checked against the results the project actually publishes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = rs.run(ROOT)

    def test_every_experiment_in_the_registry_is_accounted_for(self) -> None:
        registry = json.loads((ROOT / "experiments" / "registry.json").read_text(encoding="utf-8"))
        registered = {entry["experiment_id"] for entry in registry["experiments"]
                      if entry["experiment_id"].startswith("PROP-EXP-")}
        walked = {row["experiment_id"] for row in self.report["experiments"]}
        self.assertTrue(registered <= walked, registered - walked)

    def test_no_published_verdict_mismatches_except_the_one_on_record(self) -> None:
        mismatched = {row["experiment_id"]: sorted(item["unit"] for item in row["units"]
                                                   if item["status"] == rs.MISMATCH)
                      for row in self.report["experiments"] if row["status"] == rs.MISMATCH}
        self.assertEqual(mismatched, KNOWN_UNREPRODUCIBLE)

    def test_no_verdict_is_unverifiable_except_the_ones_on_record(self) -> None:
        unverifiable = {row["experiment_id"]: sorted(item["unit"] for item in row["units"]
                                                     if item["status"] == rs.UNVERIFIABLE)
                        for row in self.report["experiments"]
                        if any(item["status"] == rs.UNVERIFIABLE for item in row["units"])}
        self.assertEqual(unverifiable, KNOWN_UNVERIFIABLE)

    def test_the_quiz_and_chain_experiments_are_recomputed_from_real_answers(self) -> None:
        # Guards against a suite that reports agreement because it compared
        # nothing: every experiment with a verdict must have checked numbers.
        checked = {row["experiment_id"]: row.get("checks", 0) for row in self.report["experiments"]
                   if row["status"] in (rs.REPRODUCED, rs.MISMATCH)}
        self.assertGreaterEqual(len(checked), 8)
        for experiment_id, count in checked.items():
            self.assertGreater(count, 0, experiment_id)

    def test_the_verdicts_already_pinned_by_the_narrow_regrade_test_still_reproduce(self) -> None:
        by_id = {row["experiment_id"]: row for row in self.report["experiments"]}
        for experiment_id in ("PROP-EXP-MEM-004", "PROP-EXP-MEM-005"):
            self.assertEqual(by_id[experiment_id]["status"], rs.REPRODUCED, experiment_id)

    def test_the_chain_experiments_reproduce_the_effects_their_results_quote(self) -> None:
        # MEM-008's RESULT.md leads on +31.9, +16.7 and +20.8 points at hop 3;
        # recomputing them from the answers is the claim, not reading them back.
        rows = {row["experiment_id"]: row for row in self.report["experiments"]}
        units = {item["unit"]: item for item in rows["PROP-EXP-MEM-008"]["units"]}
        for document in ("clinic", "vineyard", "observatory"):
            self.assertEqual(units[document]["status"], rs.REPRODUCED, document)
            self.assertEqual(units[document]["effect"]["recomputed"],
                             units[document]["effect"]["published"], document)

    def test_the_suite_leaves_the_sealed_experiments_alone(self) -> None:
        walked = {row["experiment_id"] for row in self.report["experiments"]}
        self.assertNotIn("HOLDOUT-2026-09", walked)
        self.assertNotIn("PANEL-2026-09", walked)


if __name__ == "__main__":
    unittest.main()
