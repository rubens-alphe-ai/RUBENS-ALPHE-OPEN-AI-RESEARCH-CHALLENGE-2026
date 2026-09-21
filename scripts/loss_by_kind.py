#!/usr/bin/env python3
"""Say *which* kinds of fact a handover destroys, from answers already on disk.

Every result this project has published is a single percentage: "65% of facts
kept". A reader's next question is always the same one, and the number cannot
answer it — which facts? Losing a decorative adjective is not losing a dosage, a
deadline, or a rule that is in force. A flat rate makes loss interesting instead
of alarming, and it tells nobody what to fix.

So this re-analyses a stored benchmark folder and splits fact accuracy by the
kind of fact each question asks about, per arm and per hop, with the same paired
comparison against the control arm that `handoff_bench.summarise` performs
overall. It is deliberately a *re-analysis*: it reads the reader's stored
letters and the frozen answer key, and it makes **no model call of any kind**.
Anyone holding the stored answers can rerun it and get the same table. A
re-analysis that needed an API key would not be evidence, it would be a second
experiment.

What it refuses to do
---------------------

* **It never asks a model to classify a question.** This project's whole method
  is that no model judges anything; smuggling a classifier back in through the
  analysis would give back exactly what was removed. Kinds come from a written
  regular-expression rule, below, that anyone can read and disagree with.
* **It never reports a rate from too few questions.** A kind with three
  questions can only take the values 0, 33, 67 or 100; printing one of those as
  a percentage invites a decision the evidence cannot carry. Such a kind is
  reported as `insufficient`, with its raw counts, and no rate.
* **It never lets absent-fact questions into a fact rate.** Those questions
  measure invention, not retention, and they are kept in their own section.
* **It never repairs a stored run.** It only reads.

Where a kind comes from
-----------------------

`graph_document.py` renders both the document and the quiz from a canonical
graph of typed tuples, and its `question_for` uses one fixed sentence per kind.
`build_quiz_from_document.py` writes questions from an arbitrary document and
records no kind at all. The two sources are not symmetric and pretending
otherwise would be the dishonest part, so one written rule is applied to both,
and it is validated where ground truth exists.

The rule, in order; the first line that matches wins:

0. **reason** — the question begins "Why". This is the one kind the graph
   vocabulary does not have, and it is here because prose quizzes are full of it
   and because leaving causal questions in `unclassified` lets them dilute a
   bucket that is then reported as a rate. It is tried before everything else:
   "Why must this be reported?" asks for a cause, not for the rule.
1. **rule** — the *question* contains one of `require`, `requires`, `required`,
   `must`, `forbidden`, `mandatory`, `prohibited`, `not allowed`. Checked first,
   so "How often must X be reported?" is a rule and not a count.
2. **status** — the question begins "What is the status of".
3. **event** — the question begins "What happened" or "What happens".
4. **date** — the question begins "When" or "Since when", or contains
   "in what year", "what year", "in what month", "what month" or "on what date".
5. **count** — the question begins "How many", "How much", "How long",
   "How often", "How large", "How far", "What percentage", "What proportion" or
   "What share", or contains "by how many" or "for how long".
6. **name** — the question begins "Who", or matches "What is the <words> of".
7. Then, and only then, the *correct answer* is consulted, because a question
   stem such as "What is the earliest certification date?" carries its type in
   the answer rather than in the verb:
   **date** if the answer is a month name followed by a four-digit year, or is
   exactly a four-digit year in 1900-2099; **count** if the answer begins with a
   digit, or with a hedge ("about", "below", "over", "roughly", ...) followed by
   a digit, or with a number word up to twelve, or contains "percent".
8. Otherwise **unclassified**. About a quarter of the questions written from
   prose land here — "What did the affected batch lose?", "Where is the data
   archived?" — and they are reported as their own bucket rather than forced
   into a kind. `unclassified` is a confession, not a category.

The rule is not an opinion about English; it is an inversion of
`graph_document.question_for`, extended with the answer-shape tests that prose
quizzes need. `tests/test_loss_by_kind.py` pins it against
`experiments/graphs/depot.json`: every question the graph renderer emitted must
be classified back to the kind the graph declared, or the test fails. That is
the only ground truth available, and the rule has to survive it.

Examples:
  python scripts/loss_by_kind.py --bench experiments/PROP-EXP-MEM-014/results/depot
  python scripts/loss_by_kind.py --bench experiments/PROP-EXP-MEM-008/results/clinic \\
      --out analysis/clinic-by-kind/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_bench as hb  # noqa: E402

# The six the canonical graph declares, plus `reason`, which only a prose quiz
# ever produces and which the graph renderer cannot currently express at all.
GRAPH_KINDS = ("count", "date", "name", "rule", "status", "event")
KINDS = GRAPH_KINDS + ("reason",)
UNCLASSIFIED = "unclassified"

# A kind whose rate is computed from fewer questions than this is withheld. Five
# is where a single changed answer moves the rate by 20 percentage points; below
# that the number is an artefact of the quiz's shape, not of the handover.
MIN_QUESTIONS = 5
MIN_RUNS = 3

MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december")
NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twice|half|dozen")
HEDGES = "about|approximately|around|roughly|over|under|below|above|at least|at most|nearly|an average of|up to"

# Question-stem tests, in the order they are tried. The graph renderer's six
# templates are the first member of each group, so a graph quiz classifies
# exactly; the rest are what prose questions actually look like.
STEM_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("reason", re.compile(r"^why\b")),
    ("rule", re.compile(r"\b(requires?|required|must|forbidden|mandatory|prohibited|not allowed)\b")),
    ("status", re.compile(r"^what is the status of\b")),
    ("event", re.compile(r"^what happen(ed|s)\b")),
    ("date", re.compile(r"^(since )?when\b|\b(in what|what) (year|month)\b|\bon what date\b")),
    ("count", re.compile(r"^(how (many|much|long|often|large|far)|what (percentage|proportion|share))\b"
                         r"|\b(by how many|for how long)\b")),
    ("name", re.compile(r"^who\b|^what is the [a-z'’\- ]+ of\b")),
]

# Answer-shape tests, tried only when no stem test matched.
ANSWER_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("date", re.compile(r"^(%s)\s+(19|20)\d{2}\b" % MONTHS, re.IGNORECASE)),
    ("date", re.compile(r"^(19|20)\d{2}$")),
    ("count", re.compile(r"^((%s)\s+)?[-+]?\d" % HEDGES)),
    ("count", re.compile(r"^(%s)\b" % NUMBER_WORDS)),
    ("count", re.compile(r"\bpercent(age)?\b")),
]


def classify(question: str, answer: str = "") -> str:
    """Return one of KINDS, or `unclassified`. Deterministic; see the docstring.

    The stem decides first and the answer only breaks ties the stem left open,
    because a question's verb says what was asked for and its answer only says
    what shape the value happened to take.
    """
    stem = re.sub(r"\s+", " ", question).strip().lower()
    for kind, pattern in STEM_RULES:
        if pattern.search(stem):
            return kind
    value = re.sub(r"\s+", " ", answer).strip().lower()
    if value:
        for kind, pattern in ANSWER_RULES:
            if pattern.search(value):
                return kind
    return UNCLASSIFIED


def kinds_from_graph(quiz: dict, graph: dict) -> dict[str, str]:
    """The authoritative kind per question id, when the source graph is at hand.

    Only a graph-generated quiz can answer this; it is here so the derived rule
    can be checked against ground truth instead of merely asserted.
    """
    by_tuple = {item["id"]: item["kind"] for item in graph["tuples"]}
    return {question["id"]: by_tuple[question["tuple_id"]]
            for question in quiz["questions"] if question.get("tuple_id") in by_tuple}


def load_bench(folder: Path) -> tuple[list[dict], dict[str, str], list[dict]]:
    """Rendered questions, the frozen key, and every run that produced grades."""
    payload = json.loads((folder / "answer-key.json").read_text(encoding="utf-8"))
    rendered, key = payload["rendered"], payload["key"]
    records = []
    for path in sorted(folder.glob("*.json")):
        if path.name in ("answer-key.json", "report.json") or path.name.endswith(".failed.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("grades"):
            records.append(record)
    return rendered, key, records


def question_kinds(rendered: list[dict], key: dict[str, str],
                   authoritative: dict[str, str] | None = None) -> tuple[dict[str, str], list[str], int]:
    """Kind per fact question, the absent ids, and how many derived kinds differ.

    The correct answer text is recovered from the rendered options and the key,
    so this needs nothing the benchmark folder does not already contain.
    """
    kinds: dict[str, str] = {}
    absent: list[str] = []
    disagreements = 0
    for item in rendered:
        if item.get("kind") == "absent":
            absent.append(item["id"])
            continue
        answer = (item.get("options") or {}).get(key.get(item["id"], ""), "")
        derived = classify(item["question"], answer)
        if authoritative and item["id"] in authoritative:
            if authoritative[item["id"]] != derived:
                disagreements += 1
            kinds[item["id"]] = authoritative[item["id"]]
        else:
            kinds[item["id"]] = derived
    return kinds, absent, disagreements


def accuracy_for(record: dict, hop: str, key: dict[str, str], ids: list[str]) -> tuple[float, int]:
    """Share of one kind's questions this run answered correctly, and how many.

    Unanswered is wrong, never "does not say" — the same convention
    `handoff_quiz.grade` uses, kept here so the per-kind rates add back up to
    the published flat rate.
    """
    answers = record["grades"][hop]["answers"]
    correct = sum(1 for question_id in ids if answers.get(question_id) == key[question_id])
    return (correct / len(ids) if ids else 0.0), correct


def paired(rows_a: list[dict], rows_b: list[dict], hop: str, key: dict[str, str],
           ids: list[str]) -> list[float]:
    """Deltas over runs that both arms completed, matched by repeat number.

    `handoff_bench.summarise` zips the two arms' record lists positionally. That
    agrees with matching on the repeat number whenever both arms are complete,
    and shifts everything after a gap when one arm lost a run: vineyard's
    `facts_only-04` failed, so its published `vs_control` lines repeats 5 and 6
    up against the control's repeats 4 and 5, and reports +18.3 pp at hop 5
    where the matched comparison gives +16.7. Matching on the repeat is the same
    comparison done correctly. Where the two differ the stored report is the one
    that is wrong, and it is left exactly as it is: a published number that does
    not follow from the stored answers is a finding, not a file to edit.
    """
    by_repeat = {row["repeat"]: row for row in rows_b}
    deltas = []
    for row in rows_a:
        other = by_repeat.get(row["repeat"])
        if other is None:
            continue
        deltas.append(100.0 * (accuracy_for(row, hop, key, ids)[0] - accuracy_for(other, hop, key, ids)[0]))
    return deltas


def breakdown(records: list[dict], key: dict[str, str], kinds: dict[str, str], hop: int,
              control: str = hb.CONTROL, min_questions: int = MIN_QUESTIONS,
              min_runs: int = MIN_RUNS) -> dict:
    """Per kind, per arm: questions, runs, accuracy and the paired difference.

    A kind below the stated minimum carries counts but no rate. The counts are
    left in because they are data; the rate is withheld because it is a verdict.
    """
    hop_key = str(hop)
    by_arm: dict[str, list[dict]] = {}
    for record in records:
        if hop_key in (record.get("grades") or {}):
            by_arm.setdefault(record["strategy"], []).append(record)
    for rows in by_arm.values():
        rows.sort(key=lambda row: row["repeat"])

    by_kind: dict[str, list[str]] = {}
    for question_id, kind in kinds.items():
        by_kind.setdefault(kind, []).append(question_id)

    table: dict[str, dict] = {}
    for kind in sorted(by_kind, key=lambda name: (-len(by_kind[name]), name)):
        ids = sorted(by_kind[kind])
        entry: dict = {"questions": len(ids), "question_ids": ids, "arms": {}}
        for arm, rows in sorted(by_arm.items()):
            values = [accuracy_for(row, hop_key, key, ids) for row in rows]
            rates = [100.0 * value for value, _ in values]
            cell: dict = {"runs": len(rows), "observations": len(rows) * len(ids),
                          "correct": sum(count for _, count in values)}
            enough = len(ids) >= min_questions and len(rows) >= min_runs
            cell["sufficient"] = enough
            if not enough:
                cell["accuracy_pct"] = None
                cell["ci95"] = None
                cell["withheld_because"] = (
                    "%d questions and %d runs; a rate is reported only from at least %d questions and %d runs"
                    % (len(ids), len(rows), min_questions, min_runs))
            else:
                mean, low, high = hb.mean_ci(rates)
                cell["accuracy_pct"] = round(mean, 1)
                cell["ci95"] = [round(low, 1), round(high, 1)]
            if arm != control and control in by_arm:
                deltas = paired(rows, by_arm[control], hop_key, key, ids)
                cell["paired_runs"] = len(deltas)
                if enough and len(deltas) >= min_runs:
                    mean, low, high = hb.mean_ci(deltas)
                    cell["vs_control_pp"] = round(mean, 1)
                    cell["vs_control_ci95"] = [round(low, 1), round(high, 1)]
            entry["arms"][arm] = cell
        table[kind] = entry
    return table


def invention_by_arm(records: list[dict], hop: int) -> dict:
    """Absent-fact questions, kept apart: they measure invention, not retention."""
    hop_key = str(hop)
    out: dict[str, dict] = {}
    for record in records:
        grade = (record.get("grades") or {}).get(hop_key)
        if not grade:
            continue
        cell = out.setdefault(record["strategy"], {"runs": 0, "absent_questions_asked": 0, "inventions": 0})
        cell["runs"] += 1
        cell["absent_questions_asked"] += grade["absent_questions"]
        cell["inventions"] += grade["inventions"]
    return out


def analyse(folder: Path, control: str = hb.CONTROL, graph: dict | None = None, quiz: dict | None = None,
            min_questions: int = MIN_QUESTIONS, min_runs: int = MIN_RUNS) -> dict:
    rendered, key, records = load_bench(folder)
    authoritative = kinds_from_graph(quiz, graph) if (graph and quiz) else None
    kinds, absent, disagreements = question_kinds(rendered, key, authoritative)
    hops = sorted({int(hop) for record in records for hop in (record.get("grades") or {})})
    counts: dict[str, int] = {}
    for kind in kinds.values():
        counts[kind] = counts.get(kind, 0) + 1
    meta = {"bench": str(folder), "control": control, "hops": hops,
            "fact_questions": len(kinds), "absent_questions": len(absent),
            "runs": len(records), "min_questions": min_questions, "min_runs": min_runs,
            "kind_source": "the canonical graph" if authoritative else "the written rule in loss_by_kind.py",
            "derived_disagreements_with_graph": disagreements if authoritative else None,
            "questions_by_kind": dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))),
            "no_model_calls": True}
    return {"meta": meta, "kinds": {str(hop): breakdown(records, key, kinds, hop, control,
                                                        min_questions, min_runs) for hop in hops},
            "inventions": {str(hop): invention_by_arm(records, hop) for hop in hops},
            "question_kinds": dict(sorted(kinds.items()))}


def render_markdown(result: dict) -> str:
    meta = result["meta"]
    lines = ["# Which kinds of fact the handover loses", "",
             "Re-analysis of `%s`: %d runs, %d fact questions, %d absent-fact questions. "
             "No model was called; the reader's stored letters were compared to the key frozen before the run."
             % (meta["bench"], meta["runs"], meta["fact_questions"], meta["absent_questions"]), "",
             "Kinds come from %s. A rate is reported only for a kind with at least %d questions and %d runs; "
             "below that the counts are shown and the rate is withheld."
             % (meta["kind_source"], meta["min_questions"], meta["min_runs"]), ""]
    if meta.get("derived_disagreements_with_graph") is not None:
        lines += ["The written rule reproduces the graph's own kind for %d of %d questions."
                  % (meta["fact_questions"] - meta["derived_disagreements_with_graph"], meta["fact_questions"]), ""]

    control = meta["control"]
    for hop in sorted(result["kinds"], key=int):
        table = result["kinds"][hop]
        lines += ["## After %s handoff(s)" % hop, "",
                  "| Kind | Questions | Arm | Runs | Correct | Accuracy | 95% CI | vs control |",
                  "|---|---|---|---|---|---|---|---|"]
        for kind, entry in table.items():
            for arm, cell in entry["arms"].items():
                if not cell["sufficient"]:
                    lines.append("| %s | %d | %s | %d | %d of %d | insufficient | — | — |"
                                 % (kind, entry["questions"], arm, cell["runs"], cell["correct"],
                                    cell["observations"]))
                    continue
                if arm == control:
                    against = "control"
                elif "vs_control_pp" in cell:
                    against = "%+.1f pp (%.1f to %.1f)" % (cell["vs_control_pp"], *cell["vs_control_ci95"])
                else:
                    against = "—"
                lines.append("| %s | %d | %s | %d | %d of %d | %.1f%% | %.1f to %.1f | %s |"
                             % (kind, entry["questions"], arm, cell["runs"], cell["correct"],
                                cell["observations"], cell["accuracy_pct"], cell["ci95"][0], cell["ci95"][1],
                                against))
        lines.append("")
        inventions = result["inventions"][hop]
        lines += ["Absent-fact questions at this depth, counted apart from every kind above: "
                  + "; ".join("%s %d of %d" % (arm, cell["inventions"], cell["absent_questions_asked"])
                              for arm, cell in sorted(inventions.items())) + ".", ""]
    lines += ["`unclassified` is not a kind of fact. It is every question the written rule declined to type, "
              "and it is reported so that the classified rates cannot be read as covering the whole quiz.",
              "", "Nothing here was regenerated: the same folder, the same letters, the same key."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", type=Path, required=True, nargs="+",
                        help="one or more handoff_bench output folders, read only")
    parser.add_argument("--out", type=Path, help="folder to write loss-by-kind.json and .md into")
    parser.add_argument("--control", default=hb.CONTROL)
    parser.add_argument("--graph", type=Path, help="the canonical graph, if the quiz came from one")
    parser.add_argument("--quiz", type=Path, help="the QUIZ.json carrying tuple ids, needed with --graph")
    parser.add_argument("--min-questions", type=int, default=MIN_QUESTIONS)
    parser.add_argument("--min-runs", type=int, default=MIN_RUNS)
    args = parser.parse_args()

    if bool(args.graph) != bool(args.quiz):
        raise SystemExit("--graph and --quiz go together: the quiz carries the tuple ids the graph types")
    graph = json.loads(args.graph.read_text(encoding="utf-8")) if args.graph else None
    quiz = json.loads(args.quiz.read_text(encoding="utf-8")) if args.quiz else None

    pages, payload = [], {}
    for folder in args.bench:
        result = analyse(folder, args.control, graph, quiz, args.min_questions, args.min_runs)
        payload[str(folder)] = result
        pages.append(render_markdown(result))
    page = "\n".join(pages)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "loss-by-kind.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.out / "loss-by-kind.md").write_text(page, encoding="utf-8")
    print(page)


if __name__ == "__main__":
    main()
