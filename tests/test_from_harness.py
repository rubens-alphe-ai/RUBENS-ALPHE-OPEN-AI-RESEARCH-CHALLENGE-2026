"""Reading somebody else's harness logs: the joins, and what they refuse to pool.

Nothing here touches the network and neither harness is installed. The fixtures
are written to the schemas taken from each project's own source:

- lm-evaluation-harness, `lm_eval/evaluator.py`: the per-sample dict is
  `doc_id`, `doc`, `target`, `arguments`, `resps`, `filtered_resps`, `filter`,
  `metrics` (the names of the metric keys), `doc_hash`, `prompt_hash`,
  `target_hash`, followed by `example.update(metrics)` so each metric is a
  top-level key. `lm_eval/loggers/evaluation_tracker.py` writes one per line to
  `samples_{task}_{date}.jsonl` under a directory named for the model.
- Inspect, `inspect_ai/log/_log.py`: `EvalLog` is `version`, `status`, `eval`
  (with `model`, `task`, `task_id`), `samples`, each `EvalSample` being `id`,
  `epoch`, `input`, `target`, `scores`, `error`. `inspect_ai/scorer/_metric.py`
  defines `CORRECT = "C"`, `INCORRECT = "I"`, `PARTIAL = "P"`, `NOANSWER = "N"`.
  `inspect_ai/log/_recorders/eval.py` stores the same content in a zip as
  `header.json` plus `samples/{id}_epoch_{epoch}.json`.
- promptfoo, `src/types/index.ts`: `EvaluateSummaryV3` is `version`,
  `timestamp`, `results`, `prompts`, `stats`; each `EvaluateResult` is
  `promptIdx`, `testIdx`, `testCase`, `promptId`, `provider`
  (`Pick<ProviderOptions, 'id' | 'label'>`), `prompt`, `vars`, `response`,
  `error`, `failureReason`, `success`, `score`, `latencyMs`, `gradingResult`,
  `namedScores`, and more.
- OpenAI Evals, `evals/record.py`: the first line is
  `{"spec": dataclasses.asdict(run_spec)}`, then one `Event` per line with
  `run_id`, `event_id`, `sample_id`, `type`, `data`, `created_by`,
  `created_at`. A `"match"` event's data is
  `{"correct": bool(correct), "expected": ..., "picked": ..., **extra}`.

The risk in this file is not parsing bytes. It is the places where two runs get
lined up next to each other and could be lined up wrongly.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import from_harness as fh  # noqa: E402
import item_analysis as ia  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures, to the shapes above
# --------------------------------------------------------------------------

def lm_eval_record(doc_id: int, question: str, metric: str, value, filter_key: str = "none",
                   doc_hash: str | None = None) -> dict:
    doc = {"question": question, "answer": "A"}
    record = {
        "doc_id": doc_id,
        "doc": doc,
        "target": "A",
        "arguments": [[question, {"until": ["\n"]}]],
        "resps": [["A"]],
        "filtered_resps": ["A"],
        "filter": filter_key,
        "metrics": [metric],
        "doc_hash": doc_hash if doc_hash is not None else "hash-of-%s" % question,
        "prompt_hash": "p-%d" % doc_id,
        "target_hash": "t-%d" % doc_id,
    }
    record[metric] = value
    return record


def write_lm_eval(directory: Path, model: str, task: str, answers: dict[int, object],
                  metric: str = "acc", questions: dict[int, str] | None = None,
                  extra: list[dict] | None = None) -> Path:
    questions = questions or {i: "what is item %d" % i for i in answers}
    folder = directory / model
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("samples_%s_2026-09-22T11-04-05.123456.jsonl" % task)
    records = [lm_eval_record(i, questions[i], metric, value) for i, value in answers.items()]
    records.extend(extra or [])
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                    encoding="utf-8")
    return path


def inspect_sample(id_: str, question: str, value, scorer: str = "match",
                   epoch: int = 1, error: dict | None = None) -> dict:
    sample = {"id": id_, "epoch": epoch, "input": question, "target": "A",
              "messages": [], "error": error}
    if value is not None:
        sample["scores"] = {scorer: {"value": value, "answer": "A", "explanation": "",
                                     "metadata": {}}}
    return sample


def write_inspect_json(directory: Path, model: str, task: str, samples: list[dict],
                       name: str | None = None) -> Path:
    path = directory / (name or ("%s_%s.json" % (task, model.replace("/", "-"))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 2, "status": "success",
        "eval": {"model": model, "task": task, "task_id": "id-%s" % task,
                 "created": "2026-09-22T11:04:05"},
        "plan": {"steps": []}, "stats": {"started_at": "", "completed_at": ""},
        "samples": samples,
    }, ensure_ascii=False), encoding="utf-8")
    return path


def write_inspect_eval(directory: Path, model: str, task: str, samples: list[dict]) -> Path:
    """The zip form: header.json plus samples/{id}_epoch_{epoch}.json."""
    path = directory / ("%s_%s.eval" % (task, model.replace("/", "-")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("header.json", json.dumps({
            "version": 2, "status": "success",
            "eval": {"model": model, "task": task, "task_id": "id-%s" % task},
            "plan": {"steps": []}, "stats": {},
        }))
        archive.writestr("summaries.json", json.dumps(
            [{"id": s["id"], "epoch": s["epoch"]} for s in samples]))
        for sample in samples:
            archive.writestr("samples/%s_epoch_%d.json" % (sample["id"], sample["epoch"]),
                             json.dumps(sample, ensure_ascii=False))
    return path


def promptfoo_result(provider: str, test_idx: int, question: str, success: bool,
                     score: float | None = None, prompt_idx: int = 0,
                     error: str | None = None) -> dict:
    return {
        "id": "%s-%d" % (provider, test_idx),
        "promptIdx": prompt_idx,
        "testIdx": test_idx,
        "testCase": {"vars": {"question": question}, "assert": [{"type": "equals", "value": "A"}]},
        "promptId": "p0",
        "provider": {"id": provider, "label": provider},
        "prompt": {"raw": question, "label": "p0"},
        "vars": {"question": question},
        "response": {"output": "A"},
        "error": error,
        "failureReason": 0 if success else 1,
        "success": success,
        "score": (1.0 if success else 0.0) if score is None else score,
        "latencyMs": 12,
        "gradingResult": {"pass": success, "score": 1.0 if success else 0.0, "reason": ""},
        "namedScores": {},
    }


def write_promptfoo(directory: Path, name: str, results: list[dict],
                    version: int = 3) -> Path:
    path = directory / ("%s.json" % name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": version,
        "timestamp": "2026-09-22T11:04:05.000Z",
        "results": results,
        "prompts": [{"raw": "answer", "label": "p0"}],
        "stats": {"successes": 0, "failures": 0, "errors": 0, "tokenUsage": {}},
    }, ensure_ascii=False), encoding="utf-8")
    return path


def openai_event(run_id: str, event_id: int, sample_id: str, kind: str, data: dict) -> dict:
    return {"run_id": run_id, "event_id": event_id, "sample_id": sample_id,
            "type": kind, "data": data, "created_by": "tester",
            "created_at": "2026-09-22 11:04:05.000000+00:00"}


def write_openai_evals(directory: Path, model: str, eval_name: str,
                       answers: dict[str, object],
                       questions: dict[str, str] | None = None,
                       extra: list[dict] | None = None) -> Path:
    run_id = "run-%s" % model
    path = directory / ("%s_%s.jsonl" % (eval_name, model))
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"spec": {"completion_fns": [model], "eval_name": eval_name,
                       "base_eval": eval_name.split(".")[0], "split": "test",
                       "run_id": run_id, "created_by": "tester",
                       "run_config": {}, "created_at": "2026-09-22 11:04:05"}}]
    number = 0
    for sample, correct in answers.items():
        if questions:
            number += 1
            lines.append(openai_event(run_id, number, sample, "raw_sample",
                                      {"input": questions[sample]}))
        number += 1
        lines.append(openai_event(run_id, number, sample, "match",
                                  {"correct": correct, "expected": "A", "picked": "A"}))
    lines.extend(extra or [])
    path.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
                    encoding="utf-8")
    return path


class Temp(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.dir = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)


# --------------------------------------------------------------------------
# A clean conversion
# --------------------------------------------------------------------------

class CleanConversion(Temp):
    def test_lm_eval_three_models_become_three_respondents(self) -> None:
        answers = {"alpha": {0: 1, 1: 1, 2: 0, 3: 1},
                   "beta": {0: 1, 1: 0, 2: 0, 3: 1},
                   "gamma": {0: 1, 1: 1, 2: 1, 3: 0}}
        paths = [write_lm_eval(self.dir, model, "arc_easy", got)
                 for model, got in answers.items()]
        rows, items = fh.from_harness(paths)
        self.assertEqual(items, ["0", "1", "2", "3"])
        self.assertEqual(len(rows), 3)
        # Respondents come out sorted by name, matching assemble's ordering.
        self.assertEqual(rows[0], {"0": 1, "1": 1, "2": 0, "3": 1})
        self.assertEqual(rows[2], {"0": 1, "1": 1, "2": 1, "3": 0})

    def test_the_output_is_what_item_analysis_already_eats(self) -> None:
        """The contract, not the content: the rest of the pipeline is unchanged."""
        answers = {"alpha": {0: 1, 1: 1, 2: 0, 3: 1},
                   "beta": {0: 1, 1: 0, 2: 0, 3: 1},
                   "gamma": {0: 1, 1: 1, 2: 1, 3: 0},
                   "delta": {0: 1, 1: 0, 2: 1, 3: 0}}
        paths = [write_lm_eval(self.dir, model, "arc_easy", got)
                 for model, got in answers.items()]
        rows, items = fh.from_harness(paths)
        per_item = ia.analyse(rows, items)
        self.assertEqual([row["item"] for row in per_item], items)
        # Item 0 is answered right by everyone, which is exactly the thing the
        # item analysis exists to notice.
        self.assertEqual(per_item[0]["difficulty"], 1.0)
        self.assertIn("all but at most 5 in 100 pass it", per_item[0]["flags"])
        self.assertEqual(ia.effective_length(per_item)["items_counted"], 4)

    def test_inspect_json_and_eval_zip_read_the_same(self) -> None:
        samples = [inspect_sample("q1", "what is one", fh.CORRECT),
                   inspect_sample("q2", "what is two", fh.INCORRECT),
                   inspect_sample("q3", "what is three", fh.CORRECT)]
        as_json = write_inspect_json(self.dir / "j", "openai/gpt-4o", "gpqa", samples)
        as_zip = write_inspect_eval(self.dir / "z", "openai/gpt-4o", "gpqa", samples)
        from_json = fh.read_inspect(as_json, None, None, None)
        from_zip = fh.read_inspect(as_zip, None, None, None)
        self.assertEqual(from_json["answers"], {"q1": 1, "q2": 0, "q3": 1})
        self.assertEqual(from_json["answers"], from_zip["answers"])
        self.assertEqual(from_json["fingerprints"], from_zip["fingerprints"])
        self.assertEqual(from_zip["respondent"], "openai/gpt-4o")

    def test_inspect_takes_the_model_name_from_the_log_not_the_path(self) -> None:
        path = write_inspect_json(self.dir, "anthropic/claude-x", "gpqa",
                                  [inspect_sample("q1", "one", fh.CORRECT)],
                                  name="whatever.json")
        self.assertEqual(fh.read_inspect(path, None, None, None)["respondent"],
                         "anthropic/claude-x")

    def test_lm_eval_respondent_comes_from_the_model_directory(self) -> None:
        path = write_lm_eval(self.dir, "meta-llama__Llama-3-8B", "arc_easy", {0: 1})
        run = fh.read_lm_eval(path, None, None, None)
        self.assertEqual(run["respondent"], "meta-llama__Llama-3-8B")
        self.assertEqual(run["task"], "arc_easy")
        # And it is reported as derived, because the JSONL does not carry it.
        self.assertTrue(run["respondent_is_derived"])

    def test_a_task_name_with_underscores_survives_the_filename(self) -> None:
        path = write_lm_eval(self.dir, "alpha", "mmlu_college_chemistry", {0: 1})
        self.assertEqual(fh.lm_eval_task_name(path), "mmlu_college_chemistry")

    def test_several_tasks_for_one_model_widen_that_respondent(self) -> None:
        paths = []
        for model in ("alpha", "beta", "gamma"):
            paths.append(write_lm_eval(self.dir, model, "arc_easy", {0: 1, 1: 0}))
            paths.append(write_lm_eval(self.dir, model, "hellaswag", {0: 0, 1: 1}))
        rows, items = fh.from_harness(paths)
        # Three respondents, not six; and doc_id 0 of one task is not doc_id 0
        # of the other, so the ids are prefixed.
        self.assertEqual(len(rows), 3)
        self.assertEqual(items, ["arc_easy/0", "arc_easy/1", "hellaswag/0", "hellaswag/1"])

    def test_mixed_harnesses_are_detected_per_file(self) -> None:
        jsonl = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1})
        as_zip = write_inspect_eval(self.dir, "beta", "gpqa",
                                    [inspect_sample("q1", "one", fh.CORRECT)])
        as_json = write_inspect_json(self.dir, "gamma", "gpqa",
                                     [inspect_sample("q1", "one", fh.INCORRECT)])
        foo = write_promptfoo(self.dir, "run",
                              [promptfoo_result("openai:gpt-4o", 0, "one", True)])
        openai = write_openai_evals(self.dir, "gpt-4o", "arc.dev.v0", {"arc.dev.0": True})
        self.assertEqual(fh.detect(jsonl), "lm-eval")
        self.assertEqual(fh.detect(as_zip), "inspect")
        self.assertEqual(fh.detect(as_json), "inspect")
        self.assertEqual(fh.detect(foo), "promptfoo")
        # Both lm-eval and OpenAI Evals write .jsonl, so the suffix decides nothing.
        self.assertEqual(fh.detect(openai), "openai-evals")

    def test_promptfoo_one_file_becomes_several_respondents(self) -> None:
        questions = {0: "what is one", 1: "what is two", 2: "what is three"}
        got = {"openai:gpt-4o": [True, True, False],
               "anthropic:claude-x": [True, False, False],
               "mistral:large": [True, True, True]}
        results = [promptfoo_result(provider, i, questions[i], right)
                   for provider, marks in got.items()
                   for i, right in enumerate(marks)]
        path = write_promptfoo(self.dir, "compare", results)
        rows, items = fh.from_harness([path])
        self.assertEqual(items, ["0", "1", "2"])
        self.assertEqual(len(rows), 3)
        runs = fh.read_promptfoo(path, None, None)
        self.assertEqual([run["respondent"] for run in runs],
                         ["anthropic:claude-x", "mistral:large", "openai:gpt-4o"])

    def test_openai_evals_match_events_become_items(self) -> None:
        path = write_openai_evals(self.dir, "gpt-4o", "arc.dev.v0",
                                  {"arc.dev.0": True, "arc.dev.1": False,
                                   "arc.dev.2": True})
        run = fh.read_openai_evals(path, None)
        self.assertEqual(run["answers"], {"arc.dev.0": 1, "arc.dev.1": 0, "arc.dev.2": 1})
        self.assertEqual(run["respondent"], "gpt-4o")
        self.assertEqual(run["task"], "arc.dev.v0")

    def test_openai_evals_uses_raw_sample_to_fingerprint_the_question(self) -> None:
        questions = {"arc.dev.0": "what is one", "arc.dev.1": "what is two"}
        a = write_openai_evals(self.dir / "a", "gpt-4o", "arc.dev.v0",
                               {"arc.dev.0": True, "arc.dev.1": False}, questions)
        b = write_openai_evals(self.dir / "b", "claude-x", "arc.dev.v0",
                               {"arc.dev.0": True, "arc.dev.1": True}, questions)
        rows, items = fh.from_harness([a, b])
        self.assertEqual(items, ["arc.dev.0", "arc.dev.1"])
        _r, _i, notes = fh._run([a, b], "auto", None, None, None, None, None, None)
        self.assertEqual(notes["items_whose_identity_could_not_be_verified"], 0)


# --------------------------------------------------------------------------
# A graded score is refused, not rounded
# --------------------------------------------------------------------------

class GradedIsRefused(Temp):
    def test_lm_eval_fractional_metric_is_refused_and_names_the_other_tool(self) -> None:
        path = write_lm_eval(self.dir, "alpha", "gsm8k", {0: 1, 1: 0.5},
                             metric="exact_match")
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        message = str(caught.exception)
        self.assertIn("graded score", message)
        self.assertIn("graded_items.py", message)
        self.assertIn("doc_id 1", message)

    def test_a_rubric_arriving_as_one_to_five_is_refused(self) -> None:
        path = write_lm_eval(self.dir, "alpha", "rubric", {0: 4, 1: 2}, metric="score")
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        self.assertIn("graded_items.py", str(caught.exception))

    def test_inspect_partial_credit_is_refused(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "gpqa", [
            inspect_sample("q1", "one", fh.CORRECT),
            inspect_sample("q2", "two", fh.PARTIAL),
        ])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        message = str(caught.exception)
        self.assertIn("PARTIAL", message)
        self.assertIn("graded_items.py", message)

    def test_inspect_continuous_judge_score_is_refused(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "judged", [
            inspect_sample("q1", "one", 0.85),
        ])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("graded score", str(caught.exception))

    def test_a_score_with_several_components_is_not_one_bit(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "multi", [
            inspect_sample("q1", "one", {"accuracy": 1, "fluency": 0}),
        ])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("not a single right-or-wrong value", str(caught.exception))

    def test_promptfoo_pass_fail_over_a_graded_score_is_refused(self) -> None:
        """An llm-rubric assertion: the boolean is a threshold on a measurement."""
        path = write_promptfoo(self.dir, "rubric", [
            promptfoo_result("openai:gpt-4o", 0, "one", True, score=1.0),
            promptfoo_result("openai:gpt-4o", 1, "two", True, score=0.72)])
        with self.assertRaises(SystemExit) as caught:
            fh.read_promptfoo(path, None, None)
        message = str(caught.exception)
        self.assertIn("threshold on a graded score", message)
        self.assertIn("graded_items.py", message)
        self.assertIn("testIdx 1", message)

    def test_openai_evals_non_boolean_correct_is_refused(self) -> None:
        path = write_openai_evals(self.dir, "gpt-4o", "arc.dev.v0",
                                  {"arc.dev.0": True, "arc.dev.1": 0.5})
        with self.assertRaises(SystemExit) as caught:
            fh.read_openai_evals(path, None)
        self.assertIn("graded_items.py", str(caught.exception))

    def test_zero_and_one_as_floats_still_pass(self) -> None:
        """The refusal is of graded scores, not of the float type."""
        path = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1.0, 1: 0.0})
        self.assertEqual(fh.read_lm_eval(path, None, None, None)["answers"],
                         {"0": 1, "1": 0})


# --------------------------------------------------------------------------
# Mismatched items are refused, not pooled
# --------------------------------------------------------------------------

class MismatchedItemsRefused(Temp):
    def test_the_same_doc_id_asking_a_different_question_is_refused(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0})
        b = write_lm_eval(self.dir, "beta", "arc_easy", {0: 1, 1: 1},
                          questions={0: "what is item 0", 1: "a resampled question"})
        with self.assertRaises(SystemExit) as caught:
            fh.from_harness([a, b])
        message = str(caught.exception)
        self.assertIn("different question", message)
        self.assertIn("1:", message)
        self.assertIn("different questions", message)

    def test_matching_ids_and_matching_questions_pool_fine(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0})
        b = write_lm_eval(self.dir, "beta", "arc_easy", {0: 1, 1: 1})
        rows, items = fh.from_harness([a, b])
        self.assertEqual(items, ["0", "1"])
        self.assertEqual(len(rows), 2)

    def test_inspect_refuses_the_same_id_holding_a_different_input(self) -> None:
        a = write_inspect_json(self.dir / "a", "alpha", "gpqa", [
            inspect_sample("q1", "what is one", fh.CORRECT),
            inspect_sample("q2", "what is two", fh.INCORRECT)])
        b = write_inspect_json(self.dir / "b", "beta", "gpqa", [
            inspect_sample("q1", "what is one", fh.CORRECT),
            inspect_sample("q2", "a completely different question", fh.CORRECT)])
        with self.assertRaises(SystemExit) as caught:
            fh.from_harness([a, b])
        self.assertIn("different question", str(caught.exception))

    def test_one_respondent_cannot_hold_two_answers_to_one_item(self) -> None:
        """The guard against two models landing in one directory."""
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0})
        b = a.parent / "samples_arc_easy_2026-09-22T12-00-00.000000.jsonl"
        b.write_text(a.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            fh.from_harness([a, b])
        message = str(caught.exception)
        self.assertIn("two answers to one question", message)
        self.assertIn("label=path", message)

    def test_labels_separate_two_runs_that_share_a_directory(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0})
        b = a.parent / "samples_arc_easy_2026-09-22T12-00-00.000000.jsonl"
        b.write_text(a.read_text(encoding="utf-8"), encoding="utf-8")
        rows, items = fh.from_harness([a, b], labels={str(a): "run-1", str(b): "run-2"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(items, ["0", "1"])

    def test_two_filters_over_one_doc_id_are_refused_and_name_the_flag(self) -> None:
        extra = [lm_eval_record(0, "what is item 0", "acc", 0, filter_key="strict"),
                 lm_eval_record(1, "what is item 1", "acc", 1, filter_key="strict")]
        path = write_lm_eval(self.dir, "alpha", "gsm8k", {0: 1, 1: 0}, extra=extra)
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        message = str(caught.exception)
        self.assertIn("--filter", message)
        self.assertIn("strict", message)
        # And naming the filter resolves it rather than needing a split file.
        picked = fh.read_lm_eval(path, None, None, "strict")
        self.assertEqual(picked["answers"], {"0": 0, "1": 1})

    def test_two_metrics_are_not_chosen_between(self) -> None:
        record = lm_eval_record(0, "q", "acc", 1)
        record["metrics"] = ["acc", "acc_norm"]
        record["acc_norm"] = 0
        path = self.dir / "alpha" / "samples_arc_easy_2026-09-22T11-04-05.123456.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        self.assertIn("--metric", str(caught.exception))
        self.assertEqual(fh.read_lm_eval(path, None, "acc_norm", None)["answers"], {"0": 0})

    def test_two_scorers_are_not_chosen_between(self) -> None:
        sample = inspect_sample("q1", "one", fh.CORRECT, scorer="match")
        sample["scores"]["model_graded_qa"] = {"value": fh.INCORRECT}
        path = write_inspect_json(self.dir, "alpha", "gpqa", [sample])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("--scorer", str(caught.exception))
        self.assertEqual(fh.read_inspect(path, None, "model_graded_qa", None)["answers"],
                         {"q1": 0})

    def test_promptfoo_several_prompts_are_refused_and_name_the_flag(self) -> None:
        path = write_promptfoo(self.dir, "two-prompts", [
            promptfoo_result("openai:gpt-4o", 0, "one", True, prompt_idx=0),
            promptfoo_result("openai:gpt-4o", 0, "one", False, prompt_idx=1)])
        with self.assertRaises(SystemExit) as caught:
            fh.read_promptfoo(path, None, None)
        self.assertIn("--prompt-index", str(caught.exception))
        picked = fh.read_promptfoo(path, None, 1)
        self.assertEqual(picked[0]["answers"], {"0": 0})

    def test_promptfoo_refuses_a_summary_version_it_has_not_verified(self) -> None:
        path = write_promptfoo(self.dir, "old", [
            promptfoo_result("openai:gpt-4o", 0, "one", True)], version=2)
        with self.assertRaises(SystemExit) as caught:
            fh.read_promptfoo(path, None, None)
        self.assertIn("version 3", str(caught.exception))

    def test_promptfoo_refuses_the_same_test_index_with_different_vars(self) -> None:
        a = write_promptfoo(self.dir / "a", "run", [
            promptfoo_result("openai:gpt-4o", 0, "what is one", True)])
        b = write_promptfoo(self.dir / "b", "run", [
            promptfoo_result("anthropic:claude-x", 0, "a different question", True)])
        with self.assertRaises(SystemExit) as caught:
            fh.from_harness([a, b], prefix_items=False)
        self.assertIn("different question", str(caught.exception))

    def test_openai_evals_two_matches_for_one_sample_are_refused(self) -> None:
        extra = [openai_event("run-gpt-4o", 99, "arc.dev.0", "match",
                              {"correct": False, "expected": "A", "picked": "B"})]
        path = write_openai_evals(self.dir, "gpt-4o", "arc.dev.v0",
                                  {"arc.dev.0": True}, extra=extra)
        with self.assertRaises(SystemExit) as caught:
            fh.read_openai_evals(path, None)
        self.assertIn("more than once", str(caught.exception))

    def test_an_eval_that_records_no_match_events_is_refused(self) -> None:
        extra = [openai_event("run-x", 1, "arc.dev.0", "sampling", {"prompt": "q"}),
                 openai_event("run-x", 2, None, "final_report", {"accuracy": 0.5})]
        path = write_openai_evals(self.dir, "gpt-4o", "arc.dev.v0", {}, extra=extra)
        with self.assertRaises(SystemExit) as caught:
            fh.read_openai_evals(path, None)
        self.assertIn("no `match` events", str(caught.exception))

    def test_repeated_epochs_are_refused_rather_than_averaged(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "gpqa", [
            inspect_sample("q1", "one", fh.CORRECT, epoch=1),
            inspect_sample("q1", "one", fh.INCORRECT, epoch=2)])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("--epoch", str(caught.exception))
        self.assertEqual(fh.read_inspect(path, None, None, 2)["answers"], {"q1": 0})


# --------------------------------------------------------------------------
# An incomplete run is counted, not quietly excluded
# --------------------------------------------------------------------------

class IncompleteIsCounted(Temp):
    def test_a_model_short_of_items_shrinks_the_set_and_is_named(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0, 2: 1})
        b = write_lm_eval(self.dir, "beta", "arc_easy", {0: 1, 1: 1, 2: 0})
        short = write_lm_eval(self.dir, "gamma", "arc_easy", {0: 0, 1: 1})
        _rows, _items, notes = fh._run([a, b, short], "auto", None, None, None, None, None, None)
        self.assertEqual(notes["items_common_to_every_respondent"], 2)
        self.assertEqual(notes["items_seen_at_all"], 3)
        self.assertEqual(notes["items_dropped_for_not_being_universal"], ["2"])
        self.assertEqual(notes["items_each_respondent_was_short"], {"gamma": 1})

    def test_the_rows_are_still_rectangular_after_the_drop(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0, 2: 1})
        b = write_lm_eval(self.dir, "beta", "arc_easy", {0: 1, 1: 1, 2: 0})
        short = write_lm_eval(self.dir, "gamma", "arc_easy", {0: 0, 1: 1})
        rows, items = fh.from_harness([a, b, short])
        self.assertEqual(items, ["0", "1"])
        self.assertTrue(all(set(row) == set(items) for row in rows))

    def test_inspect_noanswer_is_missing_rather_than_wrong(self) -> None:
        """Inspect's own value_to_float maps NOANSWER to 0.0. That is right for
        an accuracy and wrong for a difficulty, so it is counted, not scored."""
        path = write_inspect_json(self.dir, "alpha", "gpqa", [
            inspect_sample("q1", "one", fh.CORRECT),
            inspect_sample("q2", "two", fh.NOANSWER),
            inspect_sample("q3", "three", fh.INCORRECT)])
        run = fh.read_inspect(path, None, None, None)
        self.assertEqual(run["answers"], {"q1": 1, "q3": 0})
        self.assertNotIn("q2", run["answers"])
        self.assertEqual(run["unrecorded"], ["q2"])

    def test_an_errored_sample_is_counted_not_failed(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "gpqa", [
            inspect_sample("q1", "one", fh.CORRECT),
            inspect_sample("q2", "two", None, error={"message": "timeout"})])
        run = fh.read_inspect(path, None, None, None)
        self.assertEqual(run["answers"], {"q1": 1})
        self.assertEqual(run["unrecorded"], ["q2"])

    def test_unrecorded_answers_reach_the_notes_by_respondent(self) -> None:
        a = write_inspect_json(self.dir / "a", "alpha", "gpqa", [
            inspect_sample("q1", "one", fh.CORRECT),
            inspect_sample("q2", "two", fh.NOANSWER)])
        b = write_inspect_json(self.dir / "b", "beta", "gpqa", [
            inspect_sample("q1", "one", fh.INCORRECT),
            inspect_sample("q2", "two", fh.CORRECT)])
        _rows, _items, notes = fh._run([a, b], "auto", None, None, None, None, None, None)
        self.assertEqual(notes["answers_the_harness_did_not_record"], {"alpha": 1})
        self.assertEqual(notes["items_each_respondent_was_short"], {"alpha": 1})
        self.assertEqual(notes["items_common_to_every_respondent"], 1)

    def test_a_promptfoo_provider_error_is_missing_not_wrong(self) -> None:
        path = write_promptfoo(self.dir, "flaky", [
            promptfoo_result("openai:gpt-4o", 0, "one", True),
            promptfoo_result("openai:gpt-4o", 1, "two", False, error="429 rate limited"),
            promptfoo_result("openai:gpt-4o", 2, "three", False)])
        run = fh.read_promptfoo(path, None, None)[0]
        self.assertEqual(run["answers"], {"0": 1, "2": 0})
        self.assertEqual(run["unrecorded"], ["1"])

    def test_a_later_fingerprint_still_guards_an_earlier_blank_one(self) -> None:
        """One log with no question text does not switch the identity check off
        for the rest: the first respondent that can prove what it was asked
        becomes the reference, and a third disagreeing with it is refused."""
        questions = {"arc.dev.0": "what is one"}
        blind = write_openai_evals(self.dir / "a", "gpt-4o", "arc.dev.v0", {"arc.dev.0": True})
        seeing = write_openai_evals(self.dir / "b", "claude-x", "arc.dev.v0",
                                    {"arc.dev.0": True}, questions)
        other = write_openai_evals(self.dir / "c", "mistral", "arc.dev.v0",
                                   {"arc.dev.0": False},
                                   {"arc.dev.0": "a completely different question"})
        with self.assertRaises(SystemExit) as caught:
            fh.from_harness([blind, seeing, other])
        self.assertIn("different question", str(caught.exception))

    def test_openai_evals_without_raw_sample_says_identity_is_unverified(self) -> None:
        """No question text in the log means the join rests on the id alone,
        and that is reported rather than passed off as a verified match."""
        a = write_openai_evals(self.dir / "a", "gpt-4o", "arc.dev.v0",
                               {"arc.dev.0": True, "arc.dev.1": False})
        b = write_openai_evals(self.dir / "b", "claude-x", "arc.dev.v0",
                               {"arc.dev.0": True, "arc.dev.1": True})
        _rows, _items, notes = fh._run([a, b], "auto", None, None, None, None, None, None)
        self.assertEqual(notes["items_whose_identity_could_not_be_verified"], 4)
        self.assertEqual(notes["items_common_to_every_respondent"], 2)

    def test_no_overlap_at_all_is_an_empty_item_set_not_a_crash(self) -> None:
        a = write_lm_eval(self.dir, "alpha", "arc_easy", {0: 1, 1: 0})
        b = write_lm_eval(self.dir, "beta", "arc_easy", {7: 1, 8: 0},
                          questions={7: "seven", 8: "eight"})
        rows, items = fh.from_harness([a, b])
        self.assertEqual(items, [])
        self.assertEqual(rows, [{}, {}])


# --------------------------------------------------------------------------
# Refusals about the shape of the file itself
# --------------------------------------------------------------------------

class MalformedIsRefused(Temp):
    def test_a_log_with_no_samples_is_refused_by_name(self) -> None:
        path = write_inspect_json(self.dir, "alpha", "gpqa", [])
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("carries no samples", str(caught.exception))

    def test_a_jsonl_without_doc_id_is_not_treated_as_lm_eval(self) -> None:
        path = self.dir / "other.jsonl"
        path.write_text(json.dumps({"question": "q", "correct": 1}) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        self.assertIn("not an lm-evaluation-harness", str(caught.exception))

    def test_a_record_with_no_metrics_key_asks_for_the_flag(self) -> None:
        record = lm_eval_record(0, "q", "acc", 1)
        del record["metrics"]
        path = self.dir / "alpha" / "samples_arc_easy_2026-09-22T11-04-05.123456.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            fh.read_lm_eval(path, None, None, None)
        self.assertIn("--metric", str(caught.exception))
        self.assertEqual(fh.read_lm_eval(path, None, "acc", None)["answers"], {"0": 1})

    def test_an_unrecognisable_file_is_named_rather_than_guessed_at(self) -> None:
        path = self.dir / "mystery.txt"
        path.write_text("trial,item,correct\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            fh.detect(path)
        self.assertIn("--harness", str(caught.exception))

    def test_a_zip_that_is_not_an_inspect_log_is_refused(self) -> None:
        path = self.dir / "not-a-log.eval"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with self.assertRaises(SystemExit) as caught:
            fh.read_inspect(path, None, None, None)
        self.assertIn("header.json", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
