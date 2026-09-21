"""Measuring a customer's own pipeline: two arms, counted failures, no trust and no keys.

Nothing here calls a paid API. The `model` kind is exercised with a fake in
place of the adapter call, the `command` kind with a python one-liner, and the
`http` kind against an http.server started inside the test — which is also the
only honest way to check that a header never leaves the file it lives in.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diagnose_report as dr  # noqa: E402
import handoff_quiz as hq  # noqa: E402
import measure_pipeline as mp  # noqa: E402

DOCUMENT = ("The clinic employs four administrative staff.\n"
            "The current accreditation runs to April 2027.\n"
            "The backup generator failed during the March storm.\n")

QUIZ = {"quiz_version": "TEST-V1", "not_stated_option": "The text does not say.", "questions": [
    {"id": "Q01", "kind": "fact", "question": "How many administrative staff?", "correct": "four",
     "distractors": ["five", "six", "seven"]},
    {"id": "Q02", "kind": "fact", "question": "When does accreditation run to?", "correct": "April 2027",
     "distractors": ["April 2026", "March 2027", "January 2028"]},
    {"id": "X01", "kind": "absent", "question": "What is the annual budget?",
     "distractors": ["100k", "250k", "1M", "5M"]},
]}

# A command pipeline that keeps only the first line, so it loses exactly one
# fact and the measurement has something to find.
FIRST_LINE = [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read().split(chr(10))[0])"]
ECHO = [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"]
EMPTY = [sys.executable, "-c", "import sys; sys.stdin.read()"]
FLOOD = [sys.executable, "-c", "import sys; sys.stdin.read(); sys.stdout.write('x' * 200000)"]
BROKEN = [sys.executable, "-c", "import sys; sys.stdin.read(); sys.stderr.write('bad mode'); sys.exit(3)"]


def text_block(prompt: str) -> str:
    """The part of the reader prompt that is the handed-over text, and nothing else."""
    return prompt.split("=== TEXT ===", 1)[1].split("=== END OF TEXT ===", 1)[0]


def honest_reader(rendered: list[dict], key: dict[str, str]):
    """A reader that answers a fact only when the fact is actually in the text.

    It stands in for the model so the whole path can be exercised for nothing.
    It is deliberately incapable of inventing: an absent question always gets
    the "does not say" letter, so any invention a test observes came from the
    code under test.
    """
    def fake_call(entry, prompt, max_tokens, limits=None):
        seen = text_block(prompt).lower()
        answers = {}
        for item in rendered:
            question = next(q for q in QUIZ["questions"] if q["id"] == item["id"])
            if item["kind"] == "fact" and question["correct"].lower() in seen:
                answers[item["id"]] = key[item["id"]]
            else:
                answers[item["id"]] = "E"
        return json.dumps({"answers": answers}), entry["model"]
    return fake_call


class Handler(BaseHTTPRequestHandler):
    """A pipeline service: upper-cases the text, and records what it was sent."""

    received: list[dict] = []
    status = 200

    def do_POST(self) -> None:  # noqa: N802 - the name http.server requires
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
        Handler.received.append({"headers": dict(self.headers), "body": body, "path": self.path})
        if Handler.status != 200:
            self.send_response(Handler.status)
            self.end_headers()
            # A service that reflects the request it was sent. Nothing in the
            # tool may read this back into an error message.
            self.wfile.write(json.dumps({"echo": dict(self.headers)}).encode("utf-8"))
            return
        payload = json.dumps({"result": {"text": body["text"].upper()}, "meta": {"ms": 3}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:
        return


class LocalService:
    def __enter__(self) -> str:
        Handler.received = []
        Handler.status = 200
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return "http://127.0.0.1:%d/transform" % self.server.server_address[1]

    def __exit__(self, *_exc) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class TemplateTests(unittest.TestCase):
    def test_the_document_is_substituted_at_any_depth_of_the_body(self) -> None:
        filled = mp.fill({"a": mp.PLACEHOLDER, "b": [{"c": "before " + mp.PLACEHOLDER}], "n": 7}, "DOC")
        self.assertEqual(filled, {"a": "DOC", "b": [{"c": "before DOC"}], "n": 7})

    def test_a_dotted_path_walks_objects_and_list_indices(self) -> None:
        payload = {"choices": [{"message": {"content": "hello"}}]}
        self.assertEqual(mp.dig(payload, "choices.0.message.content"), "hello")

    def test_a_missing_step_names_the_keys_that_were_there_and_no_values(self) -> None:
        with self.assertRaises(mp.PipelineError) as caught:
            mp.dig({"output": "secret-value-here", "status": "ok"}, "result")
        message = str(caught.exception)
        self.assertIn("output", message)
        self.assertIn("status", message)
        self.assertNotIn("secret-value-here", message)

    def test_a_path_that_lands_on_a_number_is_refused_rather_than_stringified(self) -> None:
        with self.assertRaises(mp.PipelineError):
            mp.dig({"result": 12}, "result")

    def test_a_query_string_is_never_repeated_back(self) -> None:
        self.assertEqual(mp.redact_url("https://host/x?api_key=abc"), "https://host/x")


class SpecTests(unittest.TestCase):
    def test_an_unknown_kind_is_refused_by_name(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "telepathy"}, "spec.json")
        self.assertIn("telepathy", str(caught.exception))

    def test_inline_headers_are_refused_and_the_file_is_named_instead(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "http", "url": "https://h/x", "body": {"t": mp.PLACEHOLDER},
                              "response_path": "t", "headers": {"X-Demo-Token": "fake"}}, "spec.json")
        self.assertIn("headers_file", str(caught.exception))

    def test_a_body_that_never_mentions_the_document_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "http", "url": "https://h/x", "body": {"mode": "strict"},
                              "response_path": "t"}, "spec.json")
        self.assertIn(mp.PLACEHOLDER, str(caught.exception))

    def test_a_credential_written_into_the_spec_stops_the_run(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "command", "command": ["curl", "-H", "Authorization: Bearer abc123"]},
                             "spec.json")
        self.assertIn("credential", str(caught.exception))

    def test_a_shell_string_command_is_refused_because_quoting_is_machine_specific(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "command", "command": "cat | tr a-z A-Z"}, "spec.json")
        self.assertIn("list of strings", str(caught.exception))

    def test_a_missing_required_field_names_the_field(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            mp.validate_spec({"kind": "model", "endpoint": "https://h/v1", "model": "m"}, "spec.json")
        self.assertIn("instruction", str(caught.exception))

    def test_the_description_stored_in_a_report_carries_no_query_string(self) -> None:
        spec = {"name": "vendor", "kind": "http", "url": "https://h/x?token=abc", "response_path": "t",
                "headers_file": "~/keys/h.json"}
        self.assertEqual(mp.describe(spec)["url"], "https://h/x")
        self.assertNotIn("abc", json.dumps(mp.describe(spec)))


class HttpTests(unittest.TestCase):
    def spec(self, url: str, headers_file: str | None = None) -> dict:
        spec = {"name": "vendor", "kind": "http", "url": url, "body": {"text": mp.PLACEHOLDER, "mode": "strict"},
                "response_path": "result.text", "timeout_seconds": 30}
        if headers_file:
            spec["headers_file"] = headers_file
        return mp.validate_spec(spec, "spec.json")

    def test_the_document_is_posted_and_the_declared_path_is_read_back(self) -> None:
        with LocalService() as url:
            produced = mp.http_transform(self.spec(url), DOCUMENT)
        self.assertEqual(produced, DOCUMENT.upper())
        self.assertEqual(Handler.received[0]["body"]["mode"], "strict")
        self.assertEqual(Handler.received[0]["body"]["text"], DOCUMENT)

    def test_headers_come_from_the_file_and_reach_the_service(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "headers.json"
            path.write_text(json.dumps({"X-Demo-Token": "fake-token-0000"}), encoding="utf-8")
            with LocalService() as url:
                mp.http_transform(self.spec(url, str(path)), DOCUMENT)
        self.assertEqual(Handler.received[0]["headers"].get("X-Demo-Token"), "fake-token-0000")

    def test_a_header_value_never_appears_in_an_error_even_when_the_service_echoes_it(self) -> None:
        # The failure mode this guards: a service that reflects the request in
        # its error body, and a tool that reads that body into its message.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "headers.json"
            path.write_text(json.dumps({"X-Demo-Token": "fake-token-0000"}), encoding="utf-8")
            with LocalService() as url:
                Handler.status = 500
                with self.assertRaises(mp.PipelineError) as caught:
                    mp.http_transform(self.spec(url, str(path)), DOCUMENT)
        message = str(caught.exception)
        self.assertIn("HTTP 500", message)
        self.assertNotIn("fake-token-0000", message)

    def test_the_headers_file_is_opened_at_call_time_and_not_at_load_time(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "headers.json"
            spec = self.spec("https://example.invalid/x", str(path))  # validating touches no file
            path.write_text(json.dumps({"X-Demo-Token": "written-later"}), encoding="utf-8")
            self.assertEqual(mp.read_headers(str(path)), {"X-Demo-Token": "written-later"})
            self.assertEqual(spec["headers_file"], str(path))

    def test_a_missing_headers_file_names_the_path_and_stops_the_arm(self) -> None:
        with self.assertRaises(mp.PipelineError) as caught:
            mp.read_headers(str(Path(tempfile.gettempdir()) / "no-such-headers-file.json"))
        self.assertIn("no headers file at", str(caught.exception))

    def test_a_wrong_response_path_is_a_finding_and_not_a_traceback(self) -> None:
        with LocalService() as url:
            spec = self.spec(url)
            spec["response_path"] = "result.body"
            with self.assertRaises(mp.PipelineError) as caught:
                mp.http_transform(spec, DOCUMENT)
        self.assertIn("response_path", str(caught.exception))

    def test_an_unreachable_service_is_reported_without_its_query_string(self) -> None:
        spec = self.spec("http://127.0.0.1:9/x?token=abc")
        spec["timeout_seconds"] = 2
        with self.assertRaises(mp.PipelineError) as caught:
            mp.http_transform(spec, DOCUMENT)
        self.assertNotIn("abc", str(caught.exception))


class CommandTests(unittest.TestCase):
    def test_the_document_goes_in_on_stdin_and_stdout_comes_back(self) -> None:
        produced = mp.command_transform({"kind": "command", "command": FIRST_LINE}, DOCUMENT)
        self.assertEqual(produced, "The clinic employs four administrative staff.")

    def test_a_non_zero_exit_is_a_finding_carrying_what_the_command_complained_about(self) -> None:
        with self.assertRaises(mp.PipelineError) as caught:
            mp.command_transform({"kind": "command", "command": BROKEN}, DOCUMENT)
        self.assertIn("exited 3", str(caught.exception))
        self.assertIn("bad mode", str(caught.exception))

    def test_a_command_that_does_not_exist_says_so(self) -> None:
        with self.assertRaises(mp.PipelineError) as caught:
            mp.command_transform({"kind": "command", "command": ["no-such-binary-ra-psi"]}, DOCUMENT)
        self.assertIn("no such command", str(caught.exception))

    def test_a_command_that_hangs_is_cut_off_rather_than_stalling_the_run(self) -> None:
        sleeper = [sys.executable, "-c", "import sys, time; sys.stdin.read(); time.sleep(30)"]
        with self.assertRaises(mp.PipelineError) as caught:
            mp.command_transform({"kind": "command", "command": sleeper, "timeout_seconds": 1}, DOCUMENT)
        self.assertIn("did not finish", str(caught.exception))


class ModelTests(unittest.TestCase):
    def test_the_existing_behaviour_survives_as_one_kind_among_others(self) -> None:
        seen = {}

        def fake_call(entry, prompt, max_tokens, limits=None):
            seen.update({"prompt": prompt, "entry": entry})
            return "a handover note", entry["model"]

        spec = mp.validate_spec({"kind": "model", "endpoint": "https://h/v1", "model": "m",
                                 "instruction": "Summarise this."}, "spec.json")
        with mock.patch.object(mp, "call", fake_call):
            self.assertEqual(mp.model_transform(spec, DOCUMENT), "a handover note")
        self.assertTrue(seen["prompt"].startswith(DOCUMENT))
        self.assertIn("Summarise this.", seen["prompt"])

    def test_a_provider_failure_becomes_a_counted_finding_not_a_crash(self) -> None:
        def angry(entry, prompt, max_tokens, limits=None):
            raise mp.AdapterError("HTTP 401")

        spec = {"kind": "model", "endpoint": "https://h/v1", "model": "m", "instruction": "Go."}
        with mock.patch.object(mp, "call", angry):
            with self.assertRaises(mp.PipelineError):
                mp.model_transform(spec, DOCUMENT)


class OutputTrustTests(unittest.TestCase):
    def test_an_empty_answer_is_refused(self) -> None:
        problem, flags = mp.inspect_output("   \n", DOCUMENT, "command", 10000)
        self.assertIn("empty", problem)
        self.assertEqual(flags, [])

    def test_an_absurdly_long_answer_is_refused_rather_than_truncated_in_silence(self) -> None:
        problem, _flags = mp.inspect_output("x" * 5000, DOCUMENT, "http", 1000)
        self.assertIn("over the 1000 allowed", problem)

    def test_the_input_handed_straight_back_is_named_and_not_scored_in_silence(self) -> None:
        # The most likely misconfiguration there is, and the one that would
        # otherwise score at the ceiling and be believed.
        problem, flags = mp.inspect_output(DOCUMENT, DOCUMENT, "http", 100000)
        self.assertIsNone(problem)
        self.assertEqual(flags, ["returned_input_unchanged"])

    def test_the_unchanged_check_ignores_reformatting_only(self) -> None:
        reflowed = DOCUMENT.replace("\n", "  \n ")
        self.assertEqual(mp.inspect_output(reflowed, DOCUMENT, "http", 100000)[1], ["returned_input_unchanged"])
        self.assertEqual(mp.inspect_output(DOCUMENT + " One more fact.", DOCUMENT, "http", 100000)[1], [])

    def test_the_baseline_document_arm_is_not_accused_of_echoing_itself(self) -> None:
        self.assertEqual(mp.inspect_output(DOCUMENT, DOCUMENT, "document", 100000)[1], [])


class PairingTests(unittest.TestCase):
    def rows(self, arm: str, repeats: list[int], graded: list[int]) -> list[dict]:
        return [{"strategy": arm, "repeat": index, "chain": [{"hop": 1, "sha256": "%s%d" % (arm, index)}],
                 **({"grades": {"1": {"fact_accuracy": 0.5, "inventions": 0, "absent_questions": 1}}}
                    if index in graded else {"error": "boom"})}
                for index in repeats]

    def test_a_repeat_that_failed_in_one_arm_is_dropped_from_both(self) -> None:
        records = self.rows("a", [1, 2, 3], [1, 2, 3]) + self.rows("b", [1, 2, 3], [1, 3])
        kept = mp.complete_repeats(records, ["a", "b"])
        self.assertEqual([(row["strategy"], row["repeat"]) for row in kept],
                         [("a", 1), ("a", 3), ("b", 1), ("b", 3)])

    def test_what_is_kept_is_ordered_so_the_paired_zip_pairs_like_with_like(self) -> None:
        records = self.rows("a", [1, 2], [1, 2]) + self.rows("b", [2, 1], [1, 2])
        kept = mp.complete_repeats(records, ["a", "b"])
        first = [row["repeat"] for row in kept if row["strategy"] == "a"]
        second = [row["repeat"] for row in kept if row["strategy"] == "b"]
        self.assertEqual(first, second)

    def test_an_arm_that_never_completed_leaves_nothing_to_analyse(self) -> None:
        records = self.rows("a", [1, 2], [1, 2]) + self.rows("b", [1, 2], [])
        self.assertEqual(mp.complete_repeats(records, ["a", "b"]), [])

    def test_an_arm_whose_every_run_produced_the_same_text_is_named(self) -> None:
        records = [{"strategy": "a", "repeat": i, "grades": {}, "chain": [{"hop": 1, "sha256": "same"}]}
                   for i in (1, 2)]
        records += [{"strategy": "b", "repeat": i, "grades": {}, "chain": [{"hop": 1, "sha256": "v%d" % i}]}
                    for i in (1, 2)]
        arms = {"a": {"kind": "command"}, "b": {"kind": "command"}}
        self.assertEqual(mp.frozen_arms(records, arms), ["a"])

    def test_the_untransformed_arm_is_not_warned_about_for_being_constant(self) -> None:
        # It is constant by definition; a warning that fires every run is noise.
        records = [{"strategy": "d", "repeat": i, "grades": {}, "chain": [{"hop": 1, "sha256": "same"}]}
                   for i in (1, 2)]
        self.assertEqual(mp.frozen_arms(records, {"d": {"kind": "document"}}), [])


class RunCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rendered, self.key = hq.render_quiz(QUIZ, "test")
        self.folder = tempfile.TemporaryDirectory()
        self.out = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)
        self.reader = {"evaluator_id": "r", "model": "fake-reader", "endpoint": "https://h/v1", "max_tokens": 100}

    def run_one(self, spec: dict, repeat: int = 1) -> dict:
        case = {"arm": spec.get("name", "arm"), "repeat": repeat, "spec": spec}
        with mock.patch.object(mp, "call", honest_reader(self.rendered, self.key)):
            return mp.run_case(case, DOCUMENT, QUIZ, self.rendered, self.key, self.reader,
                               self.out, None, 100000)

    def test_a_working_pipeline_is_graded_against_the_key_frozen_beforehand(self) -> None:
        spec = mp.validate_spec({"name": "firstline", "kind": "command", "command": FIRST_LINE}, "s")
        record = self.run_one(spec)
        self.assertEqual(record["grades"]["1"]["fact_correct"], 1)
        self.assertEqual(record["grades"]["1"]["inventions"], 0)
        self.assertTrue((self.out / "firstline-01.json").is_file())

    def test_the_untransformed_document_is_the_ceiling_arm(self) -> None:
        spec = mp.validate_spec({"name": "document", "kind": "document"}, "s")
        record = self.run_one(spec)
        self.assertEqual(record["grades"]["1"]["fact_accuracy"], 1.0)

    def test_an_empty_pipeline_output_is_written_down_as_a_failure(self) -> None:
        spec = mp.validate_spec({"name": "hollow", "kind": "command", "command": EMPTY}, "s")
        record = self.run_one(spec)
        self.assertNotIn("grades", record)
        self.assertIn("empty", record["error"])
        self.assertTrue((self.out / "hollow-01.failed.json").is_file())

    def test_a_flood_of_output_is_written_down_as_a_failure(self) -> None:
        spec = mp.validate_spec({"name": "flood", "kind": "command", "command": FLOOD}, "s")
        record = self.run_one(spec)
        self.assertNotIn("grades", record)
        self.assertIn("over the", record["error"])

    def test_a_pipeline_that_echoes_its_input_is_graded_but_flagged(self) -> None:
        spec = mp.validate_spec({"name": "echo", "kind": "command", "command": ECHO}, "s")
        record = self.run_one(spec)
        self.assertEqual(record["flags"], ["returned_input_unchanged"])
        self.assertEqual(record["grades"]["1"]["fact_accuracy"], 1.0)

    def test_a_stored_run_is_reused_instead_of_calling_the_pipeline_again(self) -> None:
        spec = mp.validate_spec({"name": "firstline", "kind": "command", "command": FIRST_LINE}, "s")
        self.run_one(spec)
        with mock.patch.object(mp, "transform", side_effect=AssertionError("called again")):
            record = self.run_one(spec)
        self.assertIn("grades", record)

    def test_a_reader_that_answers_with_nothing_usable_is_a_counted_failure(self) -> None:
        spec = mp.validate_spec({"name": "firstline", "kind": "command", "command": FIRST_LINE}, "s")
        case = {"arm": "firstline", "repeat": 1, "spec": spec}
        with mock.patch.object(mp, "call", lambda *a, **k: ("I would rather not.", "m")):
            record = mp.run_case(case, DOCUMENT, QUIZ, self.rendered, self.key, self.reader,
                                 self.out, None, 100000)
        self.assertIn("no usable answer", record["error"])

    def test_the_record_never_carries_the_contents_of_a_headers_file(self) -> None:
        with tempfile.TemporaryDirectory() as keys:
            path = Path(keys) / "headers.json"
            path.write_text(json.dumps({"X-Demo-Token": "fake-token-0000"}), encoding="utf-8")
            with LocalService() as url:
                spec = mp.validate_spec({"name": "vendor", "kind": "http", "url": url,
                                         "body": {"text": mp.PLACEHOLDER}, "response_path": "result.text",
                                         "headers_file": str(path)}, "s")
                record = self.run_one(spec)
        self.assertNotIn("fake-token-0000", json.dumps(record))
        self.assertEqual(record["pipeline"]["headers_file"], str(path))


class WholeRunTests(unittest.TestCase):
    """The tool end to end, and then diagnose_report.py over what it wrote."""

    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        (self.base / "doc.md").write_text(DOCUMENT, encoding="utf-8")
        (self.base / "quiz.json").write_text(json.dumps(QUIZ), encoding="utf-8")
        (self.base / "reader.key").write_text("not-a-real-key\n", encoding="utf-8")
        self.rendered, self.key = hq.render_quiz(QUIZ, "doc.md:" + QUIZ["quiz_version"])

    def spec(self, name: str, command: list[str]) -> Path:
        path = self.base / (name + ".json")
        path.write_text(json.dumps({"name": name, "kind": "command", "command": command}), encoding="utf-8")
        return path

    def invoke(self, spec: Path, out: Path, repeats: int = 3, extra: list[str] | None = None,
               reader=None) -> None:
        argv = ["measure_pipeline.py", "--document", str(self.base / "doc.md"),
                "--quiz", str(self.base / "quiz.json"), "--pipeline", str(spec),
                "--out", str(out), "--repeats", str(repeats), "--workers", "1",
                "--reader-api-key-file", str(self.base / "reader.key")] + (extra or [])
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(mp, "call", reader or honest_reader(self.rendered, self.key)):
                with mock.patch("builtins.print"):
                    mp.main()

    def test_a_lossy_pipeline_is_measured_against_the_untransformed_document(self) -> None:
        out = self.base / "run"
        self.invoke(self.spec("firstline", FIRST_LINE), out)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        table = report["by_hop"]["1"]
        self.assertEqual(report["meta"]["control"], "document")
        self.assertEqual(table["document"]["facts_kept_pct"], 100.0)
        self.assertEqual(table["firstline"]["facts_kept_pct"], 50.0)
        self.assertEqual(table["firstline"]["vs_control_pp"], -50.0)
        self.assertEqual(table["firstline"]["runs"], 3)
        self.assertTrue(report["meta"]["usability"]["usable"])

    def test_a_pipeline_that_echoes_the_document_is_named_in_the_report(self) -> None:
        out = self.base / "echo"
        self.invoke(self.spec("passthrough", ECHO), out)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["meta"]["unchanged_by_arm"]["passthrough"], 3)
        page = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("handed the document back unchanged", page)
        self.assertIn("not a result", page)

    def test_a_deterministic_pipeline_has_its_zero_width_interval_explained(self) -> None:
        out = self.base / "frozen"
        self.invoke(self.spec("firstline", FIRST_LINE), out)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertIn("firstline", report["meta"]["identical_output_arms"])
        self.assertIn("byte-identical text", (out / "report.md").read_text(encoding="utf-8"))

    def test_failures_falling_on_one_arm_alone_refuse_the_run(self) -> None:
        # The rule lives in handoff_bench.usability and is read, never re-decided.
        out = self.base / "uneven"
        honest = honest_reader(self.rendered, self.key)

        def flaky(entry, prompt, max_tokens, limits=None):
            # The reader falls over only on the shortened text, so every loss
            # lands in one arm — which is the shape that makes a paired series
            # worthless rather than merely noisy.
            if text_block(prompt).strip() == "The clinic employs four administrative staff.":
                raise mp.AdapterError("HTTP 503 upstream")
            return honest(entry, prompt, max_tokens, limits)

        self.invoke(self.spec("firstline", FIRST_LINE), out, repeats=4, reader=flaky)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        verdict = report["meta"]["usability"]
        self.assertFalse(verdict["usable"])
        self.assertEqual(verdict["failed_by_arm"], {"document": 0, "firstline": 4})
        page = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("UNUSABLE", page)

    def test_two_arms_may_both_be_pipelines(self) -> None:
        out = self.base / "two"
        self.invoke(self.spec("firstline", FIRST_LINE), out,
                    extra=["--baseline", str(self.spec("passthrough", ECHO))])
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["meta"]["control"], "passthrough")
        self.assertEqual(sorted(report["meta"]["arms"]), ["firstline", "passthrough"])
        self.assertEqual(report["by_hop"]["1"]["firstline"]["vs_control_pp"], -50.0)

    def test_two_arms_with_the_same_name_are_refused_before_anything_runs(self) -> None:
        same = self.spec("firstline", FIRST_LINE)
        with self.assertRaises(SystemExit) as caught:
            self.invoke(same, self.base / "clash", extra=["--baseline", str(same)])
        self.assertIn("distinct", str(caught.exception))

    def test_a_missing_reader_key_file_stops_the_run_before_any_pipeline_is_called(self) -> None:
        argv = ["measure_pipeline.py", "--document", str(self.base / "doc.md"),
                "--quiz", str(self.base / "quiz.json"), "--pipeline", str(self.spec("firstline", FIRST_LINE)),
                "--out", str(self.base / "nokey"), "--reader-api-key-file", str(self.base / "absent.key")]
        with mock.patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit) as caught:
                mp.main()
        self.assertIn("no API key file", str(caught.exception))

    def test_a_dry_run_reports_what_came_back_and_asks_no_reader_anything(self) -> None:
        argv = ["measure_pipeline.py", "--document", str(self.base / "doc.md"),
                "--quiz", str(self.base / "quiz.json"), "--pipeline", str(self.spec("passthrough", ECHO)),
                "--out", str(self.base / "dry"), "--dry-run"]
        printed: list[str] = []
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(mp, "call", side_effect=AssertionError("the reader was called")):
                with mock.patch("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
                    with self.assertRaises(SystemExit) as caught:
                        mp.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertTrue(any("returned_input_unchanged" in line for line in printed))
        self.assertTrue(any(line.startswith("document: ok") for line in printed))

    def test_the_report_is_rendered_by_diagnose_report_without_a_change_to_it(self) -> None:
        # The claim that makes this tool worth building: its output feeds the
        # buyer-facing page the project already has.
        out = self.base / "buyer"
        self.invoke(self.spec("firstline", FIRST_LINE), out)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        page = dr.render(report, {"recompute_command": "python scripts/regression_suite.py", "runs": {}},
                         report["meta"]["control"])
        self.assertIn("firstline", page)
        self.assertIn("100%", page)
        self.assertNotIn("%%", page)

    def test_diagnose_report_runs_as_a_command_over_this_tools_output(self) -> None:
        out = self.base / "cli"
        self.invoke(self.spec("firstline", FIRST_LINE), out)
        finished = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "diagnose_report.py"), "--bench", str(out),
             "--out", str(out / "page"), "--control", "document",
             "--document", str(self.base / "doc.md"), "--quiz", str(self.base / "quiz.json")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT))
        self.assertEqual(finished.returncode, 0, finished.stderr.decode("utf-8", "replace"))
        self.assertTrue((out / "page" / "REPORT.md").is_file())
        self.assertTrue((out / "page" / "verify.json").is_file())


if __name__ == "__main__":
    unittest.main()
