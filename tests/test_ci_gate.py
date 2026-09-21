"""What the gate fails a build for, and — harder — what it refuses to fail on."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_headroom as ch  # noqa: E402
import ci_gate as gate  # noqa: E402
import handoff_bench as hb  # noqa: E402
from handoff_quiz import T_975  # noqa: E402

CLINIC = ROOT / "experiments" / "PROP-EXP-MEM-008" / "results" / "clinic"
ARMS = ("summary", "checklist", "sections", "facts_only")


def arm_row(pct: float, half: float = 5.0, runs: int = 6, inventions: int = 0,
            asked: int = 48) -> dict:
    """One row of a `by_hop` table, in the shape `handoff_bench.summarise` writes."""
    return {"runs": runs, "facts_kept_pct": pct, "ci95": [pct - half, pct + half],
            "inventions": inventions, "absent_questions_asked": asked,
            "median_words": 120, "trimmed_runs": 0}


def make_report(rows: dict, document: str = "clinic.md", failures: list | None = None,
                repeats: int = 6) -> dict:
    return {"meta": {"document": document, "fact_questions": 23, "absent_questions": 8,
                     "read_at": [1, 3, 5], "repeats": repeats, "generator": "w", "reader": "r",
                     "word_limit": 150, "failed_runs": len(failures or []),
                     "failures": failures or []},
            "by_hop": {"5": rows}}


class GateCase(unittest.TestCase):
    """Every case writes its two reports to disk, because the gate fingerprints
    the material from files beside them and a dict in memory cannot be lied to
    the way a real repository can."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, name: str, payload: dict) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def baseline_of(self, report: dict, arm: str = "summary", margin: float = 5.0,
                    document: Path | None = None, quiz: Path | None = None,
                    replicate: dict | None = None, name: str = "base/report.json") -> dict:
        path = self.write(name, report)
        return gate.build_baseline(report, path, arm, "5", margin, document, quiz, replicate)

    def run_gate(self, baseline: dict, report: dict, margin: float | None = None,
                 document: Path | None = None, quiz: Path | None = None,
                 name: str = "now/report.json") -> dict:
        path = self.write(name, report)
        return gate.compare(baseline, report, path, margin, document, quiz)


class NoiseTests(GateCase):
    def test_a_run_compared_against_itself_is_not_a_regression(self) -> None:
        report = make_report({"summary": arm_row(61.6, half=18.4)})
        result = self.run_gate(self.baseline_of(report), report)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["exit_code"], 0)

    def test_a_drop_past_both_the_margin_and_the_noise_floor_is_a_regression(self) -> None:
        before = make_report({"summary": arm_row(88.0, half=3.0)})
        after = make_report({"summary": arm_row(60.0, half=3.0)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "REGRESSION")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("FACTS_KEPT_DROPPED", result["reason_codes"])

    def test_a_drop_inside_the_run_to_run_noise_is_not_reported_as_a_regression(self) -> None:
        # Six points, which is what this project's own replicates cannot resolve.
        # A gate that fired here would be switched off within a week.
        before = make_report({"summary": arm_row(66.0, half=18.4)})
        after = make_report({"summary": arm_row(60.0, half=18.4)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("DROP_WITHIN_NOISE", result["reason_codes"])

    def test_a_drop_past_the_margin_but_inside_the_noise_says_so_in_the_verdict(self) -> None:
        before = make_report({"summary": arm_row(66.0, half=18.4)})
        after = make_report({"summary": arm_row(60.0, half=18.4)})
        text = gate.render(self.run_gate(self.baseline_of(before), after))
        self.assertIn("inside the", text)
        self.assertIn("not reported as a regression", text)

    def test_the_verdict_always_states_the_smallest_drop_it_could_have_detected(self) -> None:
        report = make_report({"summary": arm_row(61.6, half=18.4)})
        result = self.run_gate(self.baseline_of(report), report)
        self.assertIsNotNone(result["smallest_detectable_drop_pp"])
        self.assertIn("smallest drop this comparison could have detected",
                      gate.render(result))

    def test_a_margin_finer_than_the_floor_is_reported_as_a_blind_spot_on_a_passing_run(self) -> None:
        # The gate passed, and it still has to say what it cannot see. A pass
        # that hides its own insensitivity is the failure mode that loses the
        # customer an incident later.
        report = make_report({"summary": arm_row(61.6, half=18.4)})
        result = self.run_gate(self.baseline_of(report, margin=5.0), report)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("MARGIN_BELOW_DETECTION_FLOOR", result["reason_codes"])
        self.assertIn("Blind spot", gate.render(result))
        self.assertGreater(result["repeats_needed_for_margin"], 6)

    def test_a_margin_no_affordable_repeat_count_reaches_says_to_raise_the_margin(self) -> None:
        # At the control arm's spread, two points is not a budget problem, it is
        # out of reach. Selling a repeat count that would not deliver it either
        # would be the dishonest answer.
        report = make_report({"summary": arm_row(61.6, half=18.4)})
        result = self.run_gate(self.baseline_of(report, margin=2.0), report)
        self.assertIsNone(result["repeats_needed_for_margin"])
        self.assertIn("raise the margin, not the budget", gate.render(result))

    def test_a_tighter_margin_needs_more_repeats_than_a_looser_one(self) -> None:
        self.assertGreater(gate.repeats_to_detect(2.0, 10.0), gate.repeats_to_detect(8.0, 10.0))

    def test_no_repeat_count_is_claimed_for_a_margin_of_zero(self) -> None:
        self.assertIsNone(gate.repeats_to_detect(0.0, 10.0))


class SpreadArithmeticTests(unittest.TestCase):
    def test_the_spread_recovered_from_an_interval_is_the_one_the_benchmark_started_from(self) -> None:
        values = [91.3, 86.4, 95.7, 88.0, 94.1, 90.0]
        mean, low, high = hb.mean_ci(values)
        wanted = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        self.assertAlmostEqual(gate.sd_from_ci95(low, high, len(values)), wanted, places=6)

    def test_an_interval_from_a_single_run_yields_no_spread_at_all(self) -> None:
        self.assertIsNone(gate.sd_from_ci95(70.0, 70.0, 1))

    def test_two_independent_runs_need_a_wider_floor_than_a_paired_comparison(self) -> None:
        # `check_headroom` does the paired arithmetic for two arms inside one
        # batch. A baseline recorded weeks ago shares none of that batch's
        # conditions, so the variances add instead of cancelling.
        paired = ch.smallest_passing_mean(0.0, 6, 12.0)
        independent = gate.detection_floor(12.0, 6, 12.0, 6)
        self.assertAlmostEqual(independent, paired * math.sqrt(2), places=6)

    def test_the_floor_uses_the_smaller_of_the_two_repeat_counts(self) -> None:
        # The conservative degrees of freedom: a gate should err towards saying
        # it cannot see something.
        floor = gate.detection_floor(10.0, 30, 10.0, 3)
        expected = T_975[2] * math.sqrt(100.0 / 30 + 100.0 / 3)
        self.assertAlmostEqual(floor, expected, places=6)

    def test_a_run_of_one_repeat_has_no_floor_and_nothing_can_be_told_from_noise(self) -> None:
        self.assertEqual(gate.detection_floor(10.0, 1, 10.0, 6), float("inf"))


class ReceiptTests(GateCase):
    def test_six_repeats_of_the_stored_control_arm_cannot_resolve_a_twelve_point_drop(self) -> None:
        # The receipt in docs/STATUS_RISKS.json: two identical runs of the same
        # arm gave +3.6/+5.6/+3.5 and +10.9/+2.8/+11.8, and the register says no
        # effect below about twelve points should be claimed at this budget. The
        # gate has to agree with that in code, not in prose.
        report = json.loads((CLINIC / "report.json").read_text(encoding="utf-8"))
        baseline = gate.build_baseline(report, CLINIC / "report.json", "summary", "5", 5.0, None, None, None)
        result = gate.compare(baseline, report, CLINIC / "report.json", None, None, None)
        self.assertGreater(result["detection_floor_pp"], 12.0)
        self.assertIn("MARGIN_BELOW_DETECTION_FLOOR", result["reason_codes"])

    def test_the_stored_run_compared_against_itself_passes(self) -> None:
        report = json.loads((CLINIC / "report.json").read_text(encoding="utf-8"))
        baseline = gate.build_baseline(report, CLINIC / "report.json", "checklist", "5", 5.0, None, None, None)
        result = gate.compare(baseline, report, CLINIC / "report.json", None, None, None)
        self.assertEqual(result["status"], "PASS")

    def test_two_identical_runs_that_disagreed_more_than_their_intervals_widen_the_floor(self) -> None:
        # An interval is a model of the spread; two runs of the same thing are
        # the spread. When the replicate disagrees by more than the model
        # allowed, the observed number wins.
        first = make_report({"summary": arm_row(66.0, half=2.0)})
        second = make_report({"summary": arm_row(55.1, half=2.0)})
        baseline = self.baseline_of(first, replicate=second)
        self.assertAlmostEqual(baseline["measured"]["observed_replicate_gap_pp"], 10.9, places=3)
        result = self.run_gate(baseline, make_report({"summary": arm_row(58.0, half=2.0)}))
        self.assertAlmostEqual(result["detection_floor_pp"], 10.9, places=2)
        self.assertEqual(result["status"], "PASS")


class InventionTests(GateCase):
    def test_a_single_new_invention_fails_the_build(self) -> None:
        before = make_report({"summary": arm_row(80.0, inventions=0)})
        after = make_report({"summary": arm_row(80.0, inventions=1)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "REGRESSION")
        self.assertIn("INVENTIONS_ROSE", result["reason_codes"])

    def test_a_rise_in_inventions_is_not_excused_by_the_noise_floor(self) -> None:
        # Deliberate asymmetry. A few points of retention is the same kind of
        # event as run-to-run variation; stating something the document never
        # said is not.
        before = make_report({"summary": arm_row(80.0, half=18.4, inventions=0)})
        after = make_report({"summary": arm_row(80.0, half=18.4, inventions=1)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["exit_code"], 1)

    def test_the_same_inventions_over_more_repeats_is_not_a_rise(self) -> None:
        before = make_report({"summary": arm_row(80.0, inventions=2, asked=48)})
        after = make_report({"summary": arm_row(80.0, runs=12, inventions=4, asked=96)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "PASS")

    def test_fewer_inventions_is_not_a_regression(self) -> None:
        before = make_report({"summary": arm_row(80.0, inventions=3)})
        after = make_report({"summary": arm_row(80.0, inventions=0)})
        self.assertEqual(self.run_gate(self.baseline_of(before), after)["status"], "PASS")


class UnusableTests(GateCase):
    def test_an_unusable_run_never_passes_as_no_regression_detected(self) -> None:
        before = make_report({arm: arm_row(80.0) for arm in ARMS})
        after = make_report({**{arm: arm_row(80.0) for arm in ARMS},
                             "checklist": arm_row(80.0, runs=4)},
                            failures=[{"strategy": "checklist", "repeat": r, "error": "timeout"}
                                      for r in (5, 6)])
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "CANNOT_TELL")
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("RUN_UNUSABLE", result["reason_codes"])

    def test_an_unusable_run_that_also_dropped_is_reported_as_unmeasured_not_as_a_regression(self) -> None:
        # Both directions of the same mistake. A run that may not be analysed
        # cannot supply a finding, and dressing one up as a regression is no
        # better than dressing it up as a pass.
        before = make_report({arm: arm_row(90.0, half=2.0) for arm in ARMS})
        after = make_report({**{arm: arm_row(90.0, half=2.0) for arm in ARMS},
                             "summary": arm_row(40.0, half=2.0, runs=3)},
                            failures=[{"strategy": "summary", "repeat": r, "error": "timeout"}
                                      for r in (4, 5, 6)])
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("RUN_UNUSABLE", result["reason_codes"])
        self.assertNotIn("FACTS_KEPT_DROPPED", result["reason_codes"])

    def test_a_refusal_carries_no_percentages_for_anyone_to_quote(self) -> None:
        # The same rule `handoff_bench.render_report` and `diagnose_report`
        # follow: a number printed above a refusal is the number that gets
        # quoted without the refusal.
        before = make_report({arm: arm_row(90.0) for arm in ARMS})
        after = make_report({**{arm: arm_row(90.0) for arm in ARMS}, "summary": arm_row(40.0, runs=3)},
                            failures=[{"strategy": "summary", "repeat": r, "error": "timeout"}
                                      for r in (4, 5, 6)])
        text = gate.render(self.run_gate(self.baseline_of(before), after))
        self.assertNotIn("%", text.replace("percentage points", ""))
        self.assertIn("none of them are a result", text)

    def test_failures_spread_evenly_across_arms_do_not_block_the_gate(self) -> None:
        after = make_report({arm: arm_row(80.0, runs=5) for arm in ARMS},
                            failures=[{"strategy": arm, "repeat": 6, "error": "timeout"} for arm in ARMS])
        before = make_report({arm: arm_row(80.0) for arm in ARMS})
        self.assertEqual(self.run_gate(self.baseline_of(before), after)["status"], "PASS")

    def test_a_report_with_no_stored_verdict_has_one_reconstructed_from_its_own_counts(self) -> None:
        # The stored MEM-008 runs predate `handoff_bench.usability`. The gate
        # rebuilds the records and calls that one rule rather than inventing a
        # second definition of an unusable run.
        report = make_report({arm: arm_row(80.0) for arm in ARMS})
        self.assertNotIn("usability", report["meta"])
        verdict = gate.usability_of(report, "5")
        self.assertTrue(verdict["usable"])
        self.assertTrue(verdict["reconstructed"])

    def test_a_stored_verdict_is_used_rather_than_recomputed(self) -> None:
        report = make_report({arm: arm_row(80.0) for arm in ARMS})
        report["meta"]["usability"] = {"usable": False, "reason": "declared unusable by the run itself",
                                       "failed_by_arm": {}, "runs_by_arm": {}}
        self.assertFalse(gate.usability_of(report, "5")["usable"])


class MaterialTests(GateCase):
    def test_a_baseline_records_the_material_it_was_measured_on(self) -> None:
        document = self.write("clinic.md", {"text": "unused"})
        quiz = self.write("quiz.json", {"quiz_version": "v1"})
        baseline = self.baseline_of(make_report({"summary": arm_row(80.0)}), document=document, quiz=quiz)
        self.assertEqual(baseline["material"]["document"], "clinic.md")
        self.assertEqual(len(baseline["material"]["document_sha256"]), 64)
        self.assertEqual(len(baseline["material"]["quiz_sha256"]), 64)
        self.assertEqual(baseline["measured"]["repeats"], 6)
        self.assertIsNotNone(baseline["measured"]["sd_pp"])

    def test_a_baseline_from_another_document_refuses_to_compare_rather_than_reporting_a_drop(self) -> None:
        before = make_report({"summary": arm_row(90.0, half=2.0)}, document="clinic.md")
        after = make_report({"summary": arm_row(50.0, half=2.0)}, document="vineyard.md")
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["status"], "CANNOT_TELL")
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("MATERIAL_MISMATCH", result["reason_codes"])
        self.assertNotIn("facts_kept_drop_pp", result)

    def test_a_quiz_that_grew_a_question_refuses_to_compare(self) -> None:
        before = make_report({"summary": arm_row(90.0, half=2.0)})
        after = make_report({"summary": arm_row(50.0, half=2.0)})
        after["meta"]["fact_questions"] = 24
        result = self.run_gate(self.baseline_of(before), after)
        self.assertIn("MATERIAL_MISMATCH", result["reason_codes"])

    def test_a_hash_the_baseline_pinned_and_this_run_cannot_produce_is_not_a_pass(self) -> None:
        # "We did not keep the evidence" must never report as "it checks out".
        quiz = self.write("quiz.json", {"quiz_version": "v1"})
        report = make_report({"summary": arm_row(90.0, half=2.0)})
        baseline = self.baseline_of(report, quiz=quiz)
        result = self.run_gate(baseline, report, quiz=None)
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("MATERIAL_MISMATCH", result["reason_codes"])

    def test_a_field_the_baseline_left_unpinned_is_not_held_against_the_run(self) -> None:
        report = make_report({"summary": arm_row(90.0, half=2.0)})
        baseline = self.baseline_of(report)
        self.assertIsNone(baseline["material"]["document_sha256"])
        self.assertEqual(self.run_gate(baseline, report)["status"], "PASS")

    def test_a_changed_quiz_file_is_caught_even_when_its_question_counts_match(self) -> None:
        quiz = self.write("quiz.json", {"quiz_version": "v1"})
        report = make_report({"summary": arm_row(90.0, half=2.0)})
        baseline = self.baseline_of(report, quiz=quiz)
        quiz.write_text(json.dumps({"quiz_version": "v2"}), encoding="utf-8")
        result = self.run_gate(baseline, report, quiz=quiz)
        self.assertIn("MATERIAL_MISMATCH", result["reason_codes"])


class RefusalTests(GateCase):
    def test_a_missing_arm_is_not_a_pass(self) -> None:
        before = make_report({"summary": arm_row(80.0)})
        after = make_report({"checklist": arm_row(80.0)})
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("ARM_MISSING", result["reason_codes"])

    def test_a_run_of_one_repeat_is_not_a_pass_and_is_not_a_regression(self) -> None:
        # One repeat has no spread, so nothing it shows can be told from
        # run-to-run variation. Passing would claim a comparison that was never
        # possible; failing would invent one.
        before = make_report({"summary": arm_row(90.0, half=0.0, runs=1)}, repeats=1)
        after = make_report({"summary": arm_row(40.0, half=0.0, runs=1)}, repeats=1)
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("NO_SPREAD_RECORDED", result["reason_codes"])
        self.assertIsNone(result["detection_floor_pp"])

    def test_a_single_repeat_still_fails_the_build_when_it_invents_something_new(self) -> None:
        # An invented fact is visible in one run. Retention is not.
        before = make_report({"summary": arm_row(90.0, half=0.0, runs=1, inventions=0)}, repeats=1)
        after = make_report({"summary": arm_row(90.0, half=0.0, runs=1, inventions=1)}, repeats=1)
        result = self.run_gate(self.baseline_of(before), after)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("INVENTIONS_ROSE", result["reason_codes"])

    def test_a_baseline_written_by_a_version_this_gate_does_not_know_is_refused(self) -> None:
        report = make_report({"summary": arm_row(80.0)})
        baseline = self.baseline_of(report)
        baseline["record_version"] = "SOMETHING-ELSE-V9"
        result = self.run_gate(baseline, report)
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("BASELINE_UNREADABLE", result["reason_codes"])

    def test_writing_a_baseline_for_an_arm_the_run_never_measured_is_refused(self) -> None:
        report = make_report({"summary": arm_row(80.0)})
        with self.assertRaises(SystemExit):
            self.baseline_of(report, arm="checklist")

    def test_every_verdict_ends_with_the_exit_code_it_will_use(self) -> None:
        report = make_report({"summary": arm_row(80.0)})
        for result in (self.run_gate(self.baseline_of(report), report),
                       self.run_gate(self.baseline_of(report),
                                     make_report({"summary": arm_row(80.0)}, document="other.md"))):
            self.assertIn("Exit %d" % result["exit_code"], gate.render(result))


class CommandLineTests(unittest.TestCase):
    """The exit code is the product. It is checked through the command line,
    because that is the only surface CI ever touches."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "ci_gate.py"), *args],
                              cwd=str(ROOT), capture_output=True, text=True)

    def test_the_stored_run_gates_against_its_own_baseline_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "baseline.json"
            written = self.run_cli("--report", str(CLINIC), "--arm", "checklist",
                                   "--write-baseline", str(out))
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertTrue(out.is_file())
            done = self.run_cli("--baseline", str(out), "--report", str(CLINIC))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("RA-PSI memory gate: PASS", done.stdout)

    def test_a_regression_exits_one_through_the_command_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "now").mkdir()
            dropped = json.loads((CLINIC / "report.json").read_text(encoding="utf-8"))
            dropped["by_hop"]["5"]["checklist"]["facts_kept_pct"] = 40.0
            dropped["by_hop"]["5"]["checklist"]["ci95"] = [35.0, 45.0]
            (tmp / "now" / "report.json").write_text(json.dumps(dropped), encoding="utf-8")
            # The answer key travels with the run: without it the fingerprint the
            # baseline pinned cannot be reproduced and the gate would refuse
            # before it ever compared a number.
            (tmp / "now" / "answer-key.json").write_bytes((CLINIC / "answer-key.json").read_bytes())
            out = tmp / "baseline.json"
            self.run_cli("--report", str(CLINIC), "--arm", "checklist", "--write-baseline", str(out))
            done = self.run_cli("--baseline", str(out), "--report", str(tmp / "now"))
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("This is a regression", done.stdout)

    def test_comparing_without_a_baseline_is_refused_rather_than_assumed(self) -> None:
        done = self.run_cli("--report", str(CLINIC))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--baseline", done.stderr)


if __name__ == "__main__":
    unittest.main()
