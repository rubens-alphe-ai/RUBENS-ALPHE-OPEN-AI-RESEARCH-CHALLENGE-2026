#!/usr/bin/env python3
"""Turn an evaluation harness's own logs into the three columns this project reads.

`item_analysis.py --table` wants a CSV of trial, item, correct. Every harness on
earth computes that internally — it cannot report 78% without knowing which
items were right — and every harness writes it down in a different shape. Until
this file existed, the only shape we read was HELM's published bucket, so a
prospective user had to write the conversion themselves before they could find
out whether they had a problem. Nobody spends two days to answer that question.

Four harnesses are read here, and the schema of each was taken from its own
source rather than from memory:

- **EleutherAI `lm-evaluation-harness`**, `--log_samples`. `lm_eval/evaluator.py`
  builds one dict per document with `doc_id`, `doc`, `target`, `filter`,
  `metrics` (the *names* of the metric keys) and `doc_hash`, then does
  `example.update(metrics)` so each metric lands as a top-level key.
  `lm_eval/loggers/evaluation_tracker.py` writes those one-per-line to
  `samples_{task}_{date}.jsonl`.
- **Inspect** (UK AI Security Institute). A `.json` log is an `EvalLog`:
  `eval.model`, `eval.task`, and `samples`, each sample carrying `id`, `epoch`,
  `input`, `target` and `scores` — a dict of scorer name to a `Score` whose
  `value` is `"C"`/`"I"`/`"P"`/`"N"` (from `scorer/_metric.py`) or a number. A
  `.eval` log is the same content as a zip: `header.json` plus one
  `samples/{id}_epoch_{epoch}.json` per sample, per `log/_recorders/eval.py`.
- **promptfoo**, `promptfoo eval --output results.json`. `src/types/index.ts`
  declares `EvaluateSummaryV3` as `version`, `timestamp`, `results`, `prompts`,
  `stats`, and each `EvaluateResult` as `promptIdx`, `testIdx`, `testCase`,
  `provider` (`Pick<ProviderOptions, 'id' | 'label'>`), `vars`, `error`,
  `success: boolean`, `score: number` and `gradingResult`. One file holds every
  provider, so one file becomes several respondents.
- **OpenAI Evals**, the event log written by `evals/record.py`:
  `{"spec": asdict(run_spec)}` on the first line, then one `Event` per line with
  `run_id`, `event_id`, `sample_id`, `type`, `data`. A `type` of `"match"`
  carries `data.correct`, built as `bool(correct)` — already a bit, with no
  threshold anywhere near it.

Nothing here needs any of them installed. All four are read with the standard
library, so an auditor can run this against a log without reproducing the
environment that made it.

What it refuses, and why each refusal is the point:

- **A graded score is refused, not rounded.** Inspect's `P` (partial credit) and
  any metric value that is not already 0 or 1 stop the conversion and name
  `scripts/graded_items.py`. Where the cut falls would change every number
  downstream, and that is not a decision to make inside an importer.
- **Two runs are not pooled onto an item unless they were asked the same
  question.** lm-eval writes `doc_hash` itself; for Inspect the input and target
  are hashed here. A disagreement on any shared id is refused, naming both runs.
- **An answer the harness did not record is missing, not wrong.** Inspect's
  `NOANSWER` and errored samples are counted and named, never scored zero. The
  harness's own `value_to_float` maps `NOANSWER` to 0.0; that is the right
  choice for an accuracy figure and the wrong one for an item statistic, because
  it turns a gap in the data into a failure by the respondent.
- **A metric or scorer that has to be chosen is not chosen here.** A file
  carrying both `acc` and `acc_norm`, or two scorers, is refused with the list,
  because the two answer different questions.

  python scripts/from_harness.py --out table.csv out/*/samples_arc_easy_*.jsonl
  python scripts/from_harness.py --out table.csv logs/*.eval
  python scripts/from_harness.py --out table.csv promptfoo-results.json
  python scripts/item_analysis.py --table table.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Inspect's score sentinels, from inspect_ai/scorer/_metric.py.
CORRECT, INCORRECT, PARTIAL, NOANSWER = "C", "I", "P", "N"

# Entry names inside a .eval zip, from inspect_ai/log/_recorders/eval.py.
HEADER_JSON, SAMPLES_DIR = "header.json", "samples/"

TRUTHY = {"1", "true", "t", "yes", "y", "correct", "pass", "right"}
FALSY = {"0", "false", "f", "no", "n", "incorrect", "fail", "wrong"}

GRADED_NOTE = (
    "Rounding it here would change every number downstream, and a rubric read as "
    "right-or-wrong reports a healthy instrument as dead. Use scripts/graded_items.py, "
    "which takes the scale range."
)


def digest(payload: object) -> str:
    """A short stable hash of whatever identifies a question."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def binary(value: object, where: str) -> int:
    """0 or 1, or a refusal. Never a threshold, never a round.

    `where` names the file, the item and the metric, because a refusal that does
    not say which record caused it sends its reader back to grep.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().lower()
        if text in TRUTHY:
            return 1
        if text in FALSY:
            return 0
        try:
            number = float(text)
        except ValueError:
            raise SystemExit("%s holds %r, which is neither a word for correctness nor a "
                             "number this can read as one" % (where, value))
    else:
        # A list or a dict is a score with more than one component. Picking one
        # of them, or collapsing them, is a modelling decision.
        raise SystemExit("%s holds %r, which is not a single right-or-wrong value" % (where, value))
    if number in (0.0, 1.0):
        return int(number)
    raise SystemExit("%s holds %r, which is a graded score rather than correct or incorrect. %s"
                     % (where, value, GRADED_NOTE))


def sort_key(item: str) -> tuple:
    """`id10` after `id9`, not between `id1` and `id2`."""
    head, _, tail = item.rpartition("/")
    digits = "".join(c for c in tail if c.isdigit())
    return (head, int(digits) if digits else -1, tail)


# --------------------------------------------------------------------------
# EleutherAI lm-evaluation-harness
# --------------------------------------------------------------------------

def lm_eval_task_name(path: Path) -> str:
    """The task out of `samples_{task}_{date}.jsonl`.

    The sample records themselves do not name their task — only the filename
    does. Splitting on the last underscore is safe in exactly one direction:
    `date_id` is `datetime.now().isoformat().replace(":", "-")`, which contains
    no underscore, while task names very often do (`mmlu_college_chemistry`). So
    the last chunk is the date and everything between is the task.
    """
    stem = path.stem
    parts = stem.split("_")
    if stem.startswith("samples_") and len(parts) >= 3:
        return "_".join(parts[1:-1])
    return stem


def lm_eval_respondent(path: Path) -> str:
    """Which model answered — a convention, and flagged as one.

    `evaluation_tracker.py` writes samples to
    `{output_path}/{model_name_sanitized}/samples_*.jsonl`, so the parent
    directory is the model name. But it takes a second branch: when
    `--output_path` ends in `.json`, the samples land beside that file with no
    model directory at all, and then the parent name means nothing. Nothing in
    the JSONL itself carries the model, so there is no way to tell the two cases
    apart from the log. The caller is told what was derived, and `label=path`
    overrides it.
    """
    return path.parent.name or path.stem


def read_lm_eval(path: Path, label: str | None, metric: str | None,
                 filter_name: str | None) -> dict:
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError as error:
                raise SystemExit("%s line %d is not JSON: %s" % (path, number, error))
    if not records:
        raise SystemExit("%s holds no records" % path)
    if "doc_id" not in records[0]:
        raise SystemExit("%s has no doc_id in its first record, so it is not an "
                         "lm-evaluation-harness --log_samples file" % path)

    filters = sorted({str(r.get("filter", "")) for r in records})
    if filter_name is not None:
        if filter_name not in filters:
            raise SystemExit("%s holds no records under filter %r; it has %s"
                             % (path, filter_name, ", ".join(repr(f) for f in filters)))
        records = [r for r in records if str(r.get("filter", "")) == filter_name]

    # A task run through several filters writes the same doc_id once per filter.
    # Those are different answers to the same question, and choosing between
    # them is the user's decision, not this importer's.
    names: set[str] = set()
    for record in records:
        declared = record.get("metrics")
        if isinstance(declared, list):
            names.update(str(n) for n in declared)
    if metric is not None:
        chosen = metric
    elif len(names) == 1:
        chosen = names.pop()
    elif names:
        raise SystemExit("%s reports %d metrics (%s). They answer different questions, so "
                         "pick one with --metric." % (path, len(names), ", ".join(sorted(names))))
    else:
        raise SystemExit("%s does not declare a `metrics` key, so this reader cannot tell which "
                         "of its fields is the score. Name it with --metric." % path)

    task = lm_eval_task_name(path)
    answers: dict[str, int] = {}
    fingerprints: dict[str, str] = {}
    unrecorded: list[str] = []
    seen: set[str] = set()
    for record in records:
        item = str(record["doc_id"])
        if item in seen:
            raise SystemExit(
                "%s records doc_id %s more than once (filters present: %s). Two answers to one "
                "question cannot become one bit here; select one with --filter, or split the "
                "file." % (path, item, ", ".join(repr(f) for f in filters)))
        seen.add(item)
        fingerprints[item] = str(record.get("doc_hash") or digest(record.get("doc")))
        if chosen not in record:
            # The metric is declared for the task but absent from this record:
            # an answer the harness did not score, not an answer that was wrong.
            unrecorded.append(item)
            continue
        answers[item] = binary(record[chosen], "%s doc_id %s metric %r" % (path, item, chosen))
    return {"respondent": label or lm_eval_respondent(path), "task": task, "source": str(path),
            "harness": "lm-evaluation-harness", "metric": chosen,
            "respondent_is_derived": label is None,
            "answers": answers, "fingerprints": fingerprints, "unrecorded": unrecorded}


# --------------------------------------------------------------------------
# Inspect (UK AI Security Institute)
# --------------------------------------------------------------------------

def load_inspect(path: Path) -> tuple[dict, list[dict]]:
    """Header and samples, from either the zip form or the plain JSON form."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if HEADER_JSON not in names:
                raise SystemExit("%s is a zip with no %s, so it is not an Inspect .eval log"
                                 % (path, HEADER_JSON))
            header = json.loads(archive.read(HEADER_JSON).decode("utf-8"))
            entries = sorted(n for n in names
                             if n.startswith(SAMPLES_DIR) and n.endswith(".json"))
            samples = [json.loads(archive.read(n).decode("utf-8")) for n in entries]
        return header, samples
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit("%s is neither a .eval zip nor readable JSON: %s" % (path, error))
    if not isinstance(document, dict) or "eval" not in document:
        raise SystemExit("%s has no top-level `eval` block, so it is not an Inspect log" % path)
    return document, list(document.get("samples") or [])


def read_inspect(path: Path, label: str | None, scorer: str | None,
                 epoch: int | None) -> dict:
    header, samples = load_inspect(path)
    spec = header.get("eval") or {}
    model, task = str(spec.get("model", "")), str(spec.get("task", ""))
    if not samples:
        raise SystemExit(
            "%s carries no samples. A header-only log (or one written with --no-log-samples) "
            "holds the aggregate score and not the per-item record, and the aggregate is the "
            "number this project exists to go underneath." % path)
    if not model and label is None:
        raise SystemExit("%s does not name a model in eval.model, so its respondent has no "
                         "name. Pass it as label=%s." % (path, path))

    epochs = sorted({int(s.get("epoch", 1)) for s in samples})
    if len(epochs) > 1:
        if epoch is None:
            raise SystemExit(
                "%s holds %d epochs (%s): the same questions answered more than once. Averaging "
                "repeats into one bit is a modelling decision this importer will not make. Pick "
                "one with --epoch." % (path, len(epochs), ", ".join(str(e) for e in epochs)))
        samples = [s for s in samples if int(s.get("epoch", 1)) == epoch]
        if not samples:
            raise SystemExit("%s holds no samples in epoch %d" % (path, epoch))

    present: set[str] = set()
    for sample in samples:
        present.update(str(n) for n in (sample.get("scores") or {}))
    if scorer is not None:
        if scorer not in present:
            raise SystemExit("%s has no scorer named %r; it has %s"
                             % (path, scorer, ", ".join(sorted(present)) or "none"))
        chosen = scorer
    elif len(present) == 1:
        chosen = present.pop()
    elif present:
        raise SystemExit("%s was scored by %d scorers (%s). They are different measurements of "
                         "the same answer, so pick one with --scorer."
                         % (path, len(present), ", ".join(sorted(present))))
    else:
        raise SystemExit("%s has no scores on any sample" % path)

    answers: dict[str, int] = {}
    fingerprints: dict[str, str] = {}
    unrecorded: list[str] = []
    seen: set[str] = set()
    for sample in samples:
        item = str(sample.get("id"))
        if item in seen:
            raise SystemExit("%s records sample id %s more than once in one epoch; two answers "
                             "to one question cannot become one bit here" % (path, item))
        seen.add(item)
        fingerprints[item] = digest({"input": sample.get("input"),
                                     "target": sample.get("target")})
        score = (sample.get("scores") or {}).get(chosen)
        if sample.get("error") is not None or score is None:
            # An errored sample and an unscored one are both gaps in the record.
            unrecorded.append(item)
            continue
        if not isinstance(score, dict) or "value" not in score:
            raise SystemExit("%s sample %s has a %r score of an unexpected shape (%r); an "
                             "Inspect Score is an object with a `value`" % (path, item, chosen, score))
        value = score["value"]
        if value == PARTIAL:
            raise SystemExit(
                "%s sample %s scores %r as PARTIAL. That is partial credit, which is a graded "
                "score rather than correct or incorrect. %s" % (path, item, chosen, GRADED_NOTE))
        if value == NOANSWER:
            # Inspect's own value_to_float maps NOANSWER to 0.0, which is right
            # for an accuracy and wrong for an item statistic: it converts an
            # absent answer into a wrong one, and difficulty is then a fact about
            # the harness rather than about the question.
            unrecorded.append(item)
            continue
        if value == CORRECT:
            answers[item] = 1
        elif value == INCORRECT:
            answers[item] = 0
        else:
            answers[item] = binary(value, "%s sample %s scorer %r" % (path, item, chosen))
    return {"respondent": label or model, "task": task, "source": str(path),
            "harness": "inspect", "metric": chosen, "respondent_is_derived": False,
            "answers": answers, "fingerprints": fingerprints, "unrecorded": unrecorded}


# --------------------------------------------------------------------------
# promptfoo
# --------------------------------------------------------------------------

def read_promptfoo(path: Path, label: str | None, prompt_index: int | None) -> list[dict]:
    """One results file, one respondent per provider.

    The other harnesses write one file per model. promptfoo writes one file per
    *evaluation*, holding every provider it compared — which is the shape this
    project wants anyway, since item statistics need several respondents on the
    same questions.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit("%s is not readable JSON: %s" % (path, error))
    if not isinstance(document, dict) or "results" not in document:
        raise SystemExit("%s has no top-level `results`, so it is not a promptfoo "
                         "`--output` file" % path)
    version = document.get("version")
    if version != 3:
        # Only the v3 summary has been read from promptfoo's own type
        # definitions. A v2 file is a different shape and guessing at it is
        # exactly the failure this file exists to avoid.
        raise SystemExit("%s declares summary version %r. Only version 3 (EvaluateSummaryV3) "
                         "has been verified against promptfoo's own types, and a parser written "
                         "against a guessed shape is worse than no parser." % (path, version))
    results = document.get("results")
    if not isinstance(results, list):
        raise SystemExit("%s has a `results` that is not a list of EvaluateResult" % path)
    if not results:
        raise SystemExit("%s holds no results" % path)

    prompts = sorted({r.get("promptIdx") for r in results if r.get("promptIdx") is not None})
    if len(prompts) > 1:
        if prompt_index is None:
            raise SystemExit(
                "%s compares %d prompts (promptIdx %s). The same provider answering the same "
                "test under two prompts is two answers to one question, and averaging them into "
                "one bit is a modelling decision this importer will not make. Pick one with "
                "--prompt-index." % (path, len(prompts), ", ".join(str(p) for p in prompts)))
        results = [r for r in results if r.get("promptIdx") == prompt_index]
        if not results:
            raise SystemExit("%s holds no results under promptIdx %d" % (path, prompt_index))

    task = path.stem
    runs: dict[str, dict] = {}
    for position, result in enumerate(results):
        provider = result.get("provider")
        if not isinstance(provider, dict) or not (provider.get("label") or provider.get("id")):
            raise SystemExit("%s result %d does not name a provider, so its answer has no "
                             "respondent to belong to" % (path, position))
        who = label or str(provider.get("label") or provider.get("id"))
        run = runs.setdefault(who, {
            "respondent": who, "task": task, "source": str(path), "harness": "promptfoo",
            "metric": "success", "respondent_is_derived": False,
            "answers": {}, "fingerprints": {}, "unrecorded": []})
        if result.get("testIdx") is None:
            raise SystemExit("%s result %d has no testIdx, so it cannot be attributed to an "
                             "item" % (path, position))
        item = str(result["testIdx"])
        if item in run["answers"] or item in run["unrecorded"]:
            raise SystemExit("%s holds two answers from %s to testIdx %s; two answers to one "
                             "question cannot become one bit here" % (path, who, item))
        variables = result.get("vars") or (result.get("testCase") or {}).get("vars")
        run["fingerprints"][item] = digest(variables) if variables else ""
        error = result.get("error")
        if error:
            # A provider error is a gap in the record, not an answer that was
            # wrong. promptfoo counts it as a failure for its pass rate; a
            # difficulty computed that way is a fact about the API, not the item.
            run["unrecorded"].append(item)
            continue
        score = result.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            score = None
        if score is not None and float(score) not in (0.0, 1.0):
            raise SystemExit(
                "%s scores testIdx %s at %r for %s, so its pass/fail is a threshold on a graded "
                "score (an llm-rubric or a similarity assertion). Reading only the pass/fail "
                "would throw away the measurement and keep the cut. %s"
                % (path, item, score, who, GRADED_NOTE))
        if "success" not in result:
            run["unrecorded"].append(item)
            continue
        run["answers"][item] = binary(result["success"],
                                      "%s testIdx %s for %s" % (path, item, who))
    return [runs[who] for who in sorted(runs)]


# --------------------------------------------------------------------------
# OpenAI Evals
# --------------------------------------------------------------------------

def read_openai_evals(path: Path, label: str | None) -> dict:
    events = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError as error:
                raise SystemExit("%s line %d is not JSON: %s" % (path, number, error))
    if not events:
        raise SystemExit("%s holds no events" % path)
    spec = events[0].get("spec") if isinstance(events[0], dict) else None
    if not isinstance(spec, dict):
        raise SystemExit("%s does not begin with a `spec` line, so it is not an openai/evals "
                         "event log" % path)
    completions = spec.get("completion_fns") or []
    model = "+".join(str(c) for c in completions)
    task = str(spec.get("eval_name") or spec.get("base_eval") or "")
    if not model and label is None:
        raise SystemExit("%s names no completion_fns in its spec, so its respondent has no "
                         "name. Pass it as label=%s." % (path, path))

    answers: dict[str, int] = {}
    fingerprints: dict[str, str] = {}
    unrecorded: list[str] = []
    matches = 0
    for event in events[1:]:
        if not isinstance(event, dict):
            continue
        kind, sample = event.get("type"), event.get("sample_id")
        data = event.get("data") or {}
        if kind == "raw_sample" and sample is not None:
            # Not every eval records one. Where it does, it is the question, and
            # hashing it is what lets two runs be proved comparable at all.
            fingerprints.setdefault(str(sample), digest(data))
            continue
        if kind != "match":
            continue
        matches += 1
        if sample is None:
            raise SystemExit("%s has a match event with no sample_id, so its answer cannot be "
                             "attributed to an item" % path)
        item = str(sample)
        if item in answers or item in unrecorded:
            raise SystemExit("%s records a match for sample %s more than once; two answers to "
                             "one question cannot become one bit here" % (path, item))
        if "correct" not in data:
            unrecorded.append(item)
            continue
        answers[item] = binary(data["correct"], "%s sample %s" % (path, item))
    if not matches:
        raise SystemExit(
            "%s records no `match` events, so it holds no per-item correctness. Some eval "
            "classes record only `sampling` and a `final_report`, and the aggregate is the "
            "number this project exists to go underneath." % path)
    return {"respondent": label or model, "task": task, "source": str(path),
            "harness": "openai-evals", "metric": "match.correct",
            "respondent_is_derived": False, "answers": answers,
            "fingerprints": {k: fingerprints.get(k, "") for k in answers},
            "unrecorded": unrecorded}


# --------------------------------------------------------------------------
# Detection, joining, and the counting of what was left out
# --------------------------------------------------------------------------

def detect(path: Path) -> str:
    """Which harness wrote this, from the bytes rather than from the flag.

    Guessing wrong here is safe: every reader checks for a field only its own
    format has and refuses when it is absent, so a misdetection produces a
    refusal naming the file, not a parse of the wrong schema.
    """
    if zipfile.is_zipfile(path):  # every .eval log is a zip
        return "inspect"
    try:
        with path.open(encoding="utf-8") as handle:
            head = handle.read(1 << 16)
    except OSError as error:
        raise SystemExit("cannot read %s: %s" % (path, error))
    # Order matters. lm-evaluation-harness and OpenAI Evals both write .jsonl,
    # so the suffix decides nothing; and promptfoo is checked before Inspect
    # because `"evaluationId"` should not be mistaken for Inspect's `"eval"`.
    if '"doc_id"' in head:
        return "lm-eval"
    if '"spec"' in head and '"completion_fns"' in head:
        return "openai-evals"
    if '"testIdx"' in head or '"promptIdx"' in head:
        return "promptfoo"
    if '"eval"' in head or '"samples"' in head:
        return "inspect"
    raise SystemExit("cannot tell which harness wrote %s. Name it with --harness." % path)


def read(path: Path, harness: str, label: str | None, metric: str | None,
         scorer: str | None, filter_name: str | None, epoch: int | None,
         prompt_index: int | None = None) -> list[dict]:
    """One log file becomes one respondent, or several — promptfoo holds many."""
    kind = detect(path) if harness == "auto" else harness
    if kind == "lm-eval":
        return [read_lm_eval(path, label, metric, filter_name)]
    if kind == "inspect":
        return [read_inspect(path, label, scorer, epoch)]
    if kind == "promptfoo":
        return read_promptfoo(path, label, prompt_index)
    if kind == "openai-evals":
        return [read_openai_evals(path, label)]
    raise SystemExit("unknown harness %r" % kind)


def assemble(runs: list[dict], prefix_items: bool) -> tuple[list[tuple[str, dict]], list[str], dict]:
    """Join the runs into one respondent per model, and say what was left out.

    One log file is one respondent on one task. Several files for the same
    respondent — the same model across several tasks — widen that respondent's
    item set. Several respondents on the same task give the item its variance.
    An item only some respondents were asked cannot have a difficulty, so the
    item set is the intersection, and everything outside it is counted by name.
    """
    scored: dict[str, dict[str, int]] = {}
    origin: dict[tuple[str, str], str] = {}     # (respondent, item) -> source file
    fingerprints: dict[str, tuple[str, str]] = {}  # item -> (hash, first respondent)
    conflicts: list[str] = []
    unrecorded: dict[str, int] = {}
    unverified = 0

    for run in runs:
        who = run["respondent"]
        answers = scored.setdefault(who, {})
        count = len(run["unrecorded"])
        if count:
            unrecorded[who] = unrecorded.get(who, 0) + count
        for raw, right in run["answers"].items():
            item = "%s/%s" % (run["task"], raw) if prefix_items and run["task"] else raw
            if (who, item) in origin:
                raise SystemExit(
                    "%s answers item %s in both %s and %s. The same respondent cannot hold two "
                    "answers to one question; if these are two different models, give them "
                    "names with label=path." % (who, item, origin[(who, item)], run["source"]))
            origin[(who, item)] = run["source"]
            mark = run["fingerprints"].get(raw, "")
            if not mark:
                unverified += 1
            seen = fingerprints.get(item)
            if seen is None:
                fingerprints[item] = (mark, who)
            elif not seen[0]:
                # The first respondent to reach this item carried nothing to
                # fingerprint with. A later one that does becomes the reference,
                # so a third disagreeing with it is still caught.
                if mark:
                    fingerprints[item] = (mark, who)
            elif mark and seen[0] != mark:
                conflicts.append("%s: %s was asked a different question from %s"
                                 % (item, who, seen[1]))
                continue
            answers[item] = right

    if conflicts:
        raise SystemExit(
            "the same item id does not hold the same question across respondents:\n  "
            + "\n  ".join(conflicts[:10])
            + "\nPooling these would compare respondents on different questions.")

    sets = {who: set(answers) for who, answers in scored.items()}
    everything: set[str] = set().union(*sets.values()) if sets else set()
    common: set[str] = set.intersection(*sets.values()) if sets else set()
    items = sorted(common, key=sort_key)
    respondents = [(who, scored[who]) for who in sorted(scored)]
    notes = {
        "respondents": len(scored),
        "items_common_to_every_respondent": len(common),
        "items_seen_at_all": len(everything),
        "items_dropped_for_not_being_universal": sorted(everything - common, key=sort_key),
        "items_each_respondent_was_short": {who: len(everything - got)
                                            for who, got in sorted(sets.items())
                                            if got != everything},
        "answers_the_harness_did_not_record": dict(sorted(unrecorded.items())),
        "items_whose_identity_could_not_be_verified": unverified,
        "tasks": sorted({run["task"] for run in runs if run["task"]}),
        "sources": list(dict.fromkeys(run["source"] for run in runs)),
    }
    return respondents, items, notes


def from_harness(paths: list[Path], harness: str = "auto", labels: dict[str, str] | None = None,
                 metric: str | None = None, scorer: str | None = None,
                 filter_name: str | None = None, epoch: int | None = None,
                 prefix_items: bool | None = None,
                 prompt_index: int | None = None) -> tuple[list[dict], list[str]]:
    """Harness logs in, `item_analysis.from_table`'s contract out.

    Returns exactly what `from_table` returns: one dict of item to 0/1 per
    respondent, and the item order. The rest of the pipeline cannot tell the
    difference, which is the whole point — the statistics do not change because
    the log format did.
    """
    respondents, items, notes = _run(paths, harness, labels, metric, scorer,
                                     filter_name, epoch, prefix_items, prompt_index)
    rows = [{item: answers[item] for item in items} for _who, answers in respondents]
    return rows, items


def _run(paths, harness, labels, metric, scorer, filter_name, epoch, prefix_items,
         prompt_index=None):
    labels = labels or {}
    runs = [run for path in paths
            for run in read(path, harness, labels.get(str(path)), metric, scorer,
                            filter_name, epoch, prompt_index)]
    tasks = {run["task"] for run in runs if run["task"]}
    prefix = len(tasks) > 1 if prefix_items is None else prefix_items
    return assemble(runs, prefix)


def split_label(argument: str) -> tuple[str | None, Path]:
    """`name=path`, with the path winning any `=` inside it."""
    name, sep, rest = argument.partition("=")
    if sep and rest and not Path(argument).exists():
        return name, Path(rest)
    return None, Path(argument)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("logs", nargs="+", help="harness log files; `name=path` names the respondent")
    parser.add_argument("--harness", default="auto",
                        choices=("auto", "lm-eval", "inspect", "promptfoo", "openai-evals"))
    parser.add_argument("--out", type=Path, required=True, help="CSV of trial,item,correct to write")
    parser.add_argument("--manifest", type=Path, help="where to write the provenance record")
    parser.add_argument("--metric", help="lm-eval: which metric key is correctness (acc, exact_match, ...)")
    parser.add_argument("--filter", dest="filter_name", help="lm-eval: which filter's answers to read")
    parser.add_argument("--scorer", help="Inspect: which scorer's value to read")
    parser.add_argument("--epoch", type=int, help="Inspect: which epoch to read when there are several")
    parser.add_argument("--prompt-index", type=int,
                        help="promptfoo: which promptIdx to read when several are compared")
    parser.add_argument("--prefix-items", action="store_true",
                        help="prefix item ids with the task; automatic when tasks are pooled")
    args = parser.parse_args()

    labels: dict[str, str] = {}
    paths: list[Path] = []
    for argument in args.logs:
        name, path = split_label(argument)
        if not path.is_file():
            raise SystemExit("no such log file: %s" % path)
        paths.append(path)
        if name:
            labels[str(path)] = name

    runs = [run for path in paths
            for run in read(path, args.harness, labels.get(str(path)), args.metric,
                            args.scorer, args.filter_name, args.epoch, args.prompt_index)]
    for run in runs:
        note = " (derived from the directory name, not recorded in the log)" \
            if run["respondent_is_derived"] else ""
        print("  %-28s %-22s %s%s" % (run["respondent"], run["task"], run["source"], note),
              file=sys.stderr)
    tasks = {run["task"] for run in runs if run["task"]}
    respondents, items, notes = assemble(runs, args.prefix_items or len(tasks) > 1)

    if not items:
        raise SystemExit("no item was answered by every respondent; refusing to write an empty "
                         "table. %d items were seen across %d respondents."
                         % (notes["items_seen_at_all"], notes["respondents"]))
    for who, short in notes["items_each_respondent_was_short"].items():
        print("# %s was short of %d of the %d items seen and they were dropped for everyone"
              % (who, short, notes["items_seen_at_all"]), file=sys.stderr)
    for who, count in notes["answers_the_harness_did_not_record"].items():
        print("# %s has %d items the harness recorded no answer for; they are missing, not wrong"
              % (who, count), file=sys.stderr)
    if notes["items_whose_identity_could_not_be_verified"]:
        print("# %d answers carried nothing to fingerprint the question with, so their item "
              "identity rests on the id alone"
              % notes["items_whose_identity_could_not_be_verified"], file=sys.stderr)
    if len(respondents) < 3:
        print("# only %d respondents; item_analysis.py needs more than three trials, so pool "
              "more models or more runs into this table" % len(respondents), file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial", "item", "correct"])
        writer.writeheader()
        for who, answers in respondents:
            for item in items:
                writer.writerow({"trial": who, "item": item, "correct": answers[item]})

    digests: dict[str, str] = {}
    record = {
        "record_version": "RA-PSI-HARNESS-V1",
        "harnesses": sorted({run["harness"] for run in runs}),
        "metric_note": "already 0 or 1 in the source; no threshold was chosen",
        "table": str(args.out),
        "rows": len(respondents) * len(items),
        **notes,
        "files": [{"source": run["source"], "respondent": run["respondent"],
                   "task": run["task"], "harness": run["harness"], "metric": run["metric"],
                   "sha256": digests.setdefault(
                       run["source"],
                       hashlib.sha256(Path(run["source"]).read_bytes()).hexdigest())}
                  for run in runs],
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "files"},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
