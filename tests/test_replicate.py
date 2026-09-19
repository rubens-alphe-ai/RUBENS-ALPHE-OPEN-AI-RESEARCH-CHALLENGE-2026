"""The one-command replication path: what it produces, and what it refuses to hide.

Every model call is faked. Nothing in this file may reach a provider: the point
of the script is that a stranger can run it for a few cents, and the point of
these tests is that we can change it without spending anything at all.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_quiz as hq  # noqa: E402
import replicate as rp  # noqa: E402
import validate_replication as vr  # noqa: E402
from model_adapter import AdapterError  # noqa: E402

EXPERIMENT = "PROP-EXP-MEM-005"
LOADED = rp.load_experiment(EXPERIMENT)
IDS = [item["id"] for item in LOADED["rendered"]]
FACTS = [item["id"] for item in LOADED["rendered"] if item["kind"] == "fact"]
SCHEMA = json.loads((ROOT / "schemas" / "replication-submission.schema.json").read_text(encoding="utf-8"))
# Deliberately not shaped like a real key: check_public_safety.py scans this
# tree for secret-like strings, and a convincing fake would fail that scan.
SECRET = "NOT-A-REAL-KEY-if-this-appears-anywhere-else-the-test-has-failed"

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def schema_problems(value: object, schema: dict, where: str = "") -> list[str]:
    """Check a value against the subset of JSON Schema this repository's schemas use.

    The project ships no third-party dependency and a replicator should not need
    one either, so the check is written out rather than imported. It covers what
    replication-submission.schema.json actually states: refs, types, required
    and forbidden properties, patterns, lengths and minimum item counts.
    """
    if "$ref" in schema:
        target = schema["$ref"].split("/")[-1]
        return schema_problems(value, SCHEMA["$defs"][target], where)
    found: list[str] = []
    if "const" in schema and value != schema["const"]:
        found.append("%s must be %r" % (where or "value", schema["const"]))
    kinds = schema.get("type")
    if kinds is not None:
        wanted = [kinds] if isinstance(kinds, str) else list(kinds)
        ok = False
        for kind in wanted:
            if kind == "integer":
                ok = ok or (isinstance(value, int) and not isinstance(value, bool))
            elif kind == "number":
                ok = ok or (isinstance(value, (int, float)) and not isinstance(value, bool))
            else:
                ok = ok or isinstance(value, TYPES[kind])
        if not ok:
            found.append("%s must be of type %s, not %s" % (where or "value", wanted, type(value).__name__))
            return found
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            found.append("%s is shorter than %d" % (where, schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            found.append("%s is longer than %d" % (where, schema["maxLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            found.append("%s does not match %s" % (where, schema["pattern"]))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            found.append("%s needs at least %d items" % (where, schema["minItems"]))
        for index, item in enumerate(value):
            found.extend(schema_problems(item, schema["items"], "%s[%d]" % (where, index)))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                found.append("%s is missing required %s" % (where or "the submission", name))
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            spot = "%s.%s" % (where, name) if where else name
            if name in properties:
                found.extend(schema_problems(item, properties[name], spot))
            elif extra is False:
                found.append("%s is not allowed here" % spot)
            elif isinstance(extra, dict):
                found.extend(schema_problems(item, extra, spot))
    return found


def answers_for(condition: str) -> dict[str, str]:
    """Letters from the frozen key; the baseline drops six facts, so a delta exists."""
    answers = dict(LOADED["key"])
    if condition == "baseline":
        for question in FACTS[:6]:
            answers[question] = "E"  # the "does not say" letter: not an invention, just a gap
    return answers


class Provider:
    """Every model call recorded instead of made.

    The fake tells a writer call from a reader call the way the models do: the
    reader's prompt begins with the quiz header, and the writer's begins with
    the state it was given.
    """

    def __init__(self, writer_fails: dict | None = None, reader_fails: dict | None = None,
                 reader_junk: set | None = None, handoff: str | None = None) -> None:
        self.calls: list[dict] = []
        self.writer_fails = dict(writer_fails or {})
        self.reader_fails = dict(reader_fails or {})
        self.reader_junk = set(reader_junk or ())
        self.handoff = handoff

    def __call__(self, **call: object) -> tuple[str, str]:
        self.calls.append(dict(call))
        prompt = str(call["prompt"])
        if prompt.startswith("Below is a text written by another system"):
            return self.read(prompt, call)
        return self.write(prompt, call)

    def write(self, prompt: str, call: dict) -> tuple[str, str]:
        condition = "structured" if prompt.startswith(LOADED["states"]["structured"]) else "baseline"
        seed = int(call["seed"])
        excuse = self.writer_fails.get((condition, seed)) or self.writer_fails.get(condition)
        if excuse:
            raise AdapterError(excuse)
        if self.handoff is not None:
            return self.handoff, "fake-writer"
        return ("HANDOFF-%s-seed%d. " % (condition.upper(), seed)) + "This is a handover note. " * 4, "fake-writer"

    def read(self, prompt: str, call: dict) -> tuple[str, str]:
        match = re.search(r"HANDOFF-(BASELINE|STRUCTURED)-seed(\d+)", prompt)
        condition = match.group(1).lower() if match else "baseline"
        seed = int(match.group(2)) if match else 0
        excuse = self.reader_fails.get((condition, seed)) or self.reader_fails.get(condition)
        if excuse:
            raise AdapterError(excuse)
        if (condition, seed) in self.reader_junk or condition in self.reader_junk:
            return "I would rather explain my reasoning in prose.", "fake-reader"
        return json.dumps({"answers": answers_for(condition)}), "fake-reader"


class ReplicateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.key_file = Path(self.folder.name) / "provider.key"
        self.key_file.write_text(SECRET + "\n", encoding="utf-8")
        self.original = rp.call_model
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(setattr, rp, "call_model", self.original)

    def options(self, **overrides: object) -> argparse.Namespace:
        settings = {"endpoint": "https://example.invalid/v1/chat/completions", "writer_model": "their-writer",
                    "reader_model": "their-reader", "api_key_file": str(self.key_file), "experiment": EXPERIMENT,
                    "pairs": 5, "out": Path(self.folder.name) / "submission.json", "provider": None,
                    "submitted_by": "a stranger", "notes": None, "temperature": None, "writer_max_tokens": None,
                    "reader_max_tokens": None, "extra_body": None, "retries": 2, "reader_retries": 1,
                    "pause": 0.0, "timeout": 30, "dry_run": False}
        settings.update(overrides)
        return argparse.Namespace(**settings)

    def replicate(self, provider: Provider, **overrides: object) -> tuple[dict, str]:
        """Run the whole path with the provider faked; return the outcome and what was printed."""
        rp.call_model = provider
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            outcome = rp.run(self.options(**overrides))
        return outcome, printed.getvalue()


class SubmissionTests(ReplicateTestCase):
    def test_the_submission_it_writes_satisfies_the_schema(self) -> None:
        provider = Provider()
        outcome, _ = self.replicate(provider)
        options = self.options()
        path, complete = rp.write_submission(outcome, options)
        self.assertTrue(complete)
        self.assertEqual(schema_problems(json.loads(path.read_text(encoding="utf-8")), SCHEMA), [])

    def test_the_submission_it_writes_is_accepted_by_our_own_reviewer(self) -> None:
        # The schema is the shape; validate_replication.py is the gate. A file
        # that passes one and fails the other is still friction for a stranger.
        provider = Provider()
        outcome, _ = self.replicate(provider)
        path, _ = rp.write_submission(outcome, self.options())
        report = vr.review(path, EXPERIMENT)
        self.assertEqual(report["status"], "ACCEPTED", report.get("problems"))
        self.assertEqual(report["pairs"], 5)

    def test_the_run_reports_the_paired_delta_its_interval_and_the_inventions(self) -> None:
        provider = Provider()
        outcome, _ = self.replicate(provider)
        path, complete = rp.write_submission(outcome, self.options())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            rp.report(outcome, path, complete)
        text = printed.getvalue()
        self.assertIn("paired delta", text)
        self.assertIn("95% CI", text)
        self.assertIn("inventions:", text)
        self.assertIn(str(path), text)
        self.assertIn("issue", text)

    def test_totals_are_not_asserted_in_the_submission(self) -> None:
        # The receiving project regrades. A sender's arithmetic is never used,
        # so offering it would only invite an argument about it.
        provider = Provider()
        outcome, _ = self.replicate(provider)
        path, _ = rp.write_submission(outcome, self.options())
        submission = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(submission["pairs"][0]["baseline"]), {"handoff", "answers"})
        for pair in submission["pairs"]:
            self.assertNotIn("grade", pair)

    def test_a_pair_uses_one_seed_for_both_conditions(self) -> None:
        provider = Provider()
        outcome, _ = self.replicate(provider, pairs=5)
        for pair in outcome["pairs"]:
            self.assertIn("HANDOFF-BASELINE-seed%d" % pair["seed"], pair["baseline"]["handoff"])
            self.assertIn("HANDOFF-STRUCTURED-seed%d" % pair["seed"], pair["structured"]["handoff"])
        self.assertEqual([pair["seed"] for pair in outcome["pairs"]], LOADED["generation"]["seeds"][:5])


class RenderingTests(ReplicateTestCase):
    def test_the_quiz_it_sends_is_the_one_handoff_quiz_renders(self) -> None:
        # Option order is derived from the experiment id and the quiz version.
        # A second implementation of that shuffle would drift, and every letter
        # a replicator sent us would then mean something else.
        provider = Provider()
        self.replicate(provider, pairs=1)
        reader_prompts = [str(call["prompt"]) for call in provider.calls
                          if str(call["prompt"]).startswith("Below is a text")]
        self.assertEqual(len(reader_prompts), 2)
        quiz = LOADED["quiz"]
        rendered, _key = hq.render_quiz(quiz, EXPERIMENT + ":" + quiz["quiz_version"])
        handoff = ("HANDOFF-BASELINE-seed%d. " % LOADED["generation"]["seeds"][0]) + "This is a handover note. " * 4
        self.assertEqual(reader_prompts[0], hq.reader_prompt(quiz, rendered, handoff))

    def test_every_question_offers_its_options_in_the_frozen_order(self) -> None:
        provider = Provider()
        self.replicate(provider, pairs=1)
        prompt = str(provider.calls[1]["prompt"])
        for item in LOADED["rendered"]:
            for letter, text in item["options"].items():
                self.assertIn("  %s) %s\n" % (letter, text), prompt)
            self.assertEqual(item["options"]["E"], LOADED["quiz"]["not_stated_option"])


class FailureTests(ReplicateTestCase):
    def test_a_failed_trial_is_counted_and_its_pair_is_dropped(self) -> None:
        provider = Provider(writer_fails={("structured", LOADED["generation"]["seeds"][1]): "provider returned HTTP 400: bad model"})
        outcome, printed = self.replicate(provider, pairs=5)
        self.assertEqual(len(outcome["pairs"]), 4)
        self.assertEqual(outcome["lost"], {"baseline": 0, "structured": 1})
        self.assertEqual([item["stage"] for item in outcome["log"]], ["writer"])
        self.assertIn("writer failed", printed)
        self.assertNotIn("pair-02", [pair["pair_id"] for pair in outcome["pairs"]])

    def test_losses_that_fall_on_one_condition_are_called_out(self) -> None:
        provider = Provider(writer_fails={("structured", LOADED["generation"]["seeds"][1]): "provider returned HTTP 400: bad model"})
        outcome, _ = self.replicate(provider, pairs=5)
        path, complete = rp.write_submission(outcome, self.options())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            rp.report(outcome, path, complete)
        text = printed.getvalue()
        self.assertIn("uneven across conditions", text)
        self.assertIn("pairs lost: 0 in baseline, 1 in structured", text)

    def test_a_run_short_of_five_pairs_is_not_offered_as_a_submission(self) -> None:
        provider = Provider(writer_fails={"structured": "provider returned HTTP 401: unauthorized"})
        outcome, _ = self.replicate(provider, pairs=5)
        path, complete = rp.write_submission(outcome, self.options())
        self.assertFalse(complete)
        self.assertIn(".incomplete", path.name)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            rp.report(outcome, path, complete)
        self.assertIn("INCOMPLETE", printed.getvalue())
        self.assertIn("should not be sent", printed.getvalue())

    def test_a_transient_error_is_retried_and_every_attempt_is_still_counted(self) -> None:
        provider = Provider(reader_fails={("baseline", LOADED["generation"]["seeds"][0]): "provider returned HTTP 429: slow down"})
        outcome, _ = self.replicate(provider, pairs=1, retries=2)
        self.assertEqual(len(outcome["pairs"]), 0)
        # Three attempts, all recorded: a retry that left no trace would let an
        # uneven failure rate pass for a clean run.
        self.assertEqual([item["attempt"] for item in outcome["log"]], [1, 2, 3])
        self.assertTrue(all(item["transient"] for item in outcome["log"]))

    def test_an_error_that_will_not_fix_itself_is_not_retried(self) -> None:
        provider = Provider(writer_fails={"baseline": "provider returned HTTP 401: invalid api key"})
        outcome, _ = self.replicate(provider, pairs=1, retries=3)
        self.assertEqual(len(outcome["log"]), 1)
        self.assertFalse(outcome["log"][0]["transient"])

    def test_an_unusable_reader_answer_is_asked_again_then_counted(self) -> None:
        provider = Provider(reader_junk={"baseline"})
        outcome, printed = self.replicate(provider, pairs=1, reader_retries=1)
        self.assertEqual(len(outcome["pairs"]), 0)
        self.assertEqual(len(outcome["log"]), 2)
        self.assertIn("no usable letters", outcome["log"][0]["error"])
        self.assertIn("no usable letters", printed)

    def test_a_handoff_too_short_to_submit_is_refused_before_it_reaches_the_file(self) -> None:
        # The schema requires 50 characters. Sending a one-word answer onward
        # would produce a file the receiving project refuses, after the calls
        # had already been paid for.
        provider = Provider(handoff="too short")
        outcome, printed = self.replicate(provider, pairs=1)
        self.assertEqual(len(outcome["pairs"]), 0)
        self.assertIn("must be at least 50", printed)

    def test_a_missing_key_file_stops_the_run_before_any_call(self) -> None:
        provider = Provider()
        rp.call_model = provider
        options = self.options(api_key_file=str(Path(self.folder.name) / "absent.key"))
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                rp.run(options)
        self.assertIn("no API key file", str(caught.exception))
        self.assertEqual(provider.calls, [])

    def test_an_empty_key_file_stops_the_run_before_any_call(self) -> None:
        provider = Provider()
        rp.call_model = provider
        self.key_file.write_text("", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                rp.run(self.options())
        self.assertIn("is empty", str(caught.exception))
        self.assertEqual(provider.calls, [])

    def test_an_unknown_experiment_names_the_file_it_could_not_find(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            rp.load_experiment("PROP-EXP-NOT-A-THING")
        self.assertIn("evaluation_policy.json", str(caught.exception))

    def test_repeated_handoffs_are_reported_because_they_would_be_refused(self) -> None:
        identical = "The same handover note every time, which is what a greedy sampler produces. " * 2
        provider = Provider(handoff=identical)
        outcome, _ = self.replicate(provider, pairs=5)
        self.assertTrue(rp.duplicate_handoffs(outcome["pairs"]))
        path, complete = rp.write_submission(outcome, self.options())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            rp.report(outcome, path, complete)
        self.assertIn("identical handoffs are refused", printed.getvalue())
        self.assertEqual(vr.review(path, EXPERIMENT)["status"], "REFUSED")


class KeyTests(ReplicateTestCase):
    def test_the_key_is_never_written_into_the_submission_or_printed(self) -> None:
        provider = Provider()
        outcome, printed = self.replicate(provider)
        path, _ = rp.write_submission(outcome, self.options())
        written = path.read_text(encoding="utf-8")
        self.assertNotIn(SECRET, written)
        self.assertNotIn(SECRET, printed)
        self.assertNotIn(SECRET, json.dumps(outcome["log"]))

    def test_the_script_passes_the_path_and_never_reads_the_key(self) -> None:
        # Resolving the key is the adapter's job, at call time. If this script
        # ever held the value, every error string and every dump would become a
        # place for it to escape.
        provider = Provider()
        self.replicate(provider, pairs=1)
        for call in provider.calls:
            self.assertEqual(call["api_key_file"], str(self.key_file))
            self.assertNotIn(SECRET, json.dumps({k: v for k, v in call.items() if isinstance(v, str)}))

    def test_one_model_on_both_ends_is_flagged_before_the_calls_are_paid_for(self) -> None:
        provider = Provider()
        _outcome, printed = self.replicate(provider, pairs=1, writer_model="same", reader_model="Same")
        self.assertIn("writer and the reader are the same model", printed)

    def test_a_dry_run_checks_the_inputs_and_calls_nothing(self) -> None:
        provider = Provider()
        outcome, printed = self.replicate(provider, dry_run=True)
        self.assertEqual(outcome["status"], "DRY_RUN")
        self.assertEqual(provider.calls, [])
        self.assertIn("no model was called", printed)


if __name__ == "__main__":
    unittest.main()
