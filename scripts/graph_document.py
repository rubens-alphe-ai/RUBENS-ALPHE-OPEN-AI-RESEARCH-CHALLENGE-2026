#!/usr/bin/env python3
"""Generate a document and its quiz from a graph, so the key exists before the text.

Proposed by the Moltbook agent `zhaoxuan`, in reply to MEM-012's finding that a
word-overlap proxy cannot tell a changed value from a kept one:

> A clean next experiment could instead begin from a machine-readable canonical
> graph of entity–relation–value–polarity–time tuples, render prose from it,
> hide the graph from the writer, and let the evaluator compare fetched/carried
> tuple IDs to that external gold structure. That tests typed coverage without
> asking you to mark your own homework.

Every document this project has measured was short prose written by the project
itself, and every quiz was written by a model and then checked. Both facts are
listed as limits in every result file. This removes them together:

- **No model builds the measurement.** The graph is the gold structure; the
  document is rendered from it and the quiz is derived from it, both by code.
  `scripts/build_quiz_from_document.py` needed a writer and a checker model and
  dropped whatever it could not verify. Here there is nothing to verify: the
  answer was fixed before the sentence existed.
- **An absent-fact question is absent by construction**, not by asking a second
  model whether it could answer. A probe names an entity the document mentions
  and a relation the graph does not hold for it.
- **Difficulty becomes a parameter.** Fact count, value types, polarity, and how
  much the facts about one entity spread across paragraphs are all inputs. What
  MEM-009 said a proper test of dispersion would require — varying it on purpose
  rather than observing it — becomes possible.

What this does **not** establish is that prose rendered from a graph decays like
prose someone wrote. If it does not, everything measured on it is an artefact of
the renderer. That is a bridge experiment, registered separately, and it has to
pass before any result from a generated document means anything.

  python scripts/graph_document.py --graph graphs/clinic.json --out experiments/X/
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# One template per relation kind. They are plain declarative sentences because
# the thing being measured is what survives a handoff, not what survives a
# stylist: a renderer with voice would put its own fingerprints on the decay.
TEMPLATES = {
    # The relation is the verb. An earlier version forced "has" here and produced
    # "Cancellations has 1.8 percent", which is not a sentence a handoff would
    # ever have to carry — and a renderer that writes badly would be measuring
    # its own grammar rather than the decay of prose.
    "count": "{entity} {relation} {value}.",
    "date": "{entity} was {relation} in {value}.",
    "name": "The {relation} of {entity} is {value}.",
    "rule": "{entity} requires {value}.",
    "status": "{entity} is {value}.",
    "event": "In {time}, {entity} {relation}: {value}.",
}
NEGATED = {
    "count": "{entity} does not {relation} {value}.",
    "date": "{entity} was not {relation} in {value}.",
    "name": "The {relation} of {entity} is not {value}.",
    "rule": "{entity} does not require {value}.",
    "status": "{entity} is not {value}.",
    "event": "In {time}, {entity} did not {relation}: {value}.",
}


def render_tuple(item: dict) -> str:
    table = NEGATED if item.get("polarity") == "negate" else TEMPLATES
    template = table.get(item["kind"], TEMPLATES["status"])
    return template.format(entity=item["entity"], relation=item.get("relation", ""),
                           value=item["value"], time=item.get("time", "") or "that period").strip()


def render_document(graph: dict, seed: str, spread: int = 0) -> str:
    """Prose from the graph, grouped by entity, in a fixed order.

    `spread` controls how far the facts about one entity are scattered across
    paragraphs: 0 keeps them together, higher values interleave them. It is the
    dispersion knob, and it exists so dispersion can be set rather than found.
    """
    rng = random.Random("%s|%s" % (seed, spread))
    by_entity: dict[str, list[dict]] = {}
    for item in graph["tuples"]:
        by_entity.setdefault(item["entity"], []).append(item)
    sentences = [render_tuple(item) for items in by_entity.values() for item in items]
    if spread:
        for _ in range(spread):
            rng.shuffle(sentences)
    # Sentences are packed into paragraphs of a few, keeping their order. Most
    # entities carry one fact, so grouping strictly by entity gave one sentence
    # per paragraph — a list, not prose, and a handoff of a list does not decay
    # like a handoff of prose.
    per_paragraph = max(1, int(graph.get("sentences_per_paragraph", 4)))
    blocks = [sentences[start:start + per_paragraph]
              for start in range(0, len(sentences), per_paragraph)]
    lines = ["# %s" % graph["title"], ""]
    for block in blocks:
        lines.append(" ".join(block))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def question_for(item: dict) -> str:
    return {
        "count": "How many does %s have?" % item["entity"],
        "date": "When was %s %s?" % (item["entity"], item.get("relation", "recorded")),
        "name": "What is the %s of %s?" % (item.get("relation", "name"), item["entity"]),
        "rule": "What does %s require?" % item["entity"],
        "status": "What is the status of %s?" % item["entity"],
        "event": "What happened to %s in %s?" % (item["entity"], item.get("time", "that period")),
    }.get(item["kind"], "What is recorded about %s?" % item["entity"])


def distractors_for(item: dict, graph: dict, count: int = 3) -> list[str]:
    """Wrong options of the same kind that the graph does not contain.

    A distractor drawn from the graph could be true of something else in the
    document, and a reader picking it would be marked wrong for finding a fact.
    These come from the graph's declared `decoys` pool instead, and any that
    collide with a real value are dropped rather than adjusted.
    """
    real = {entry["value"] for entry in graph["tuples"]}
    pool = [value for value in graph.get("decoys", {}).get(item["kind"], []) if value not in real]
    if len(pool) < count:
        raise ValueError("graph declares too few decoys of kind %r: %d available, %d needed"
                         % (item["kind"], len(pool), count))
    rng = random.Random("%s|%s" % (graph["graph_version"], item["id"]))
    return rng.sample(pool, count)


def answer_for(item: dict) -> str:
    """The answer the rendered document actually supports, polarity included.

    This returned `item["value"]` regardless of polarity, which made the key
    say "fully staffed" for a document that says "is **not** fully staffed".
    Three of the depot graph's thirty questions were affected. The reader
    answered "the text does not say" to all three in every one of 24 runs — it
    was right and the key was wrong — and every absolute figure in MEM-014 was
    depressed by a uniform 10 points as a result.

    The whole point of generating the quiz from the graph is that the key is
    correct by construction rather than by a model's say-so. It was incorrect by
    construction instead, which is worse, because nothing downstream could
    notice.
    """
    if item.get("polarity") == "negate":
        return "not " + item["value"]
    return item["value"]


def build_quiz(graph: dict, not_stated: str = "The text does not say.") -> dict:
    """The quiz the graph already contains, in the format the pipeline uses."""
    questions = []
    for index, item in enumerate(graph["tuples"], start=1):
        correct = answer_for(item)
        distractors = distractors_for(item, graph)
        if item.get("value") in distractors:
            # For a negated tuple the un-negated value is the one wrong answer a
            # reader might defend, so it must never be offered as a distractor.
            raise ValueError("%s offers its own un-negated value as a distractor" % item["id"])
        questions.append({"id": "Q%02d" % index, "kind": "fact", "question": question_for(item),
                          "correct": correct, "distractors": distractors,
                          "polarity": item.get("polarity", "affirm"), "tuple_id": item["id"]})
    for index, probe in enumerate(graph.get("absent_probes", []), start=1):
        # Absent by construction: the entity appears in the document, the
        # relation does not exist for it anywhere in the graph. Nothing has to
        # ask a model whether the answer is really missing.
        held = {(entry["entity"], entry.get("relation")) for entry in graph["tuples"]}
        if (probe["entity"], probe.get("relation")) in held:
            raise ValueError("absent probe %r is answered by the graph" % probe)
        questions.append({"id": "X%02d" % index, "kind": "absent",
                          "question": question_for({**probe, "kind": probe.get("kind", "status")}),
                          "distractors": probe["distractors"]})
    return {"quiz_version": graph["graph_version"], "not_stated_option": not_stated,
            "source": "generated from a canonical graph; no model wrote or checked any question",
            "questions": questions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="folder to write document.md and QUIZ.json into")
    parser.add_argument("--spread", type=int, default=0, help="how far one entity's facts scatter across paragraphs")
    args = parser.parse_args()

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    document = render_document(graph, graph["graph_version"], args.spread)
    quiz = build_quiz(graph)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "document.md").write_text(document, encoding="utf-8")
    (args.out / "QUIZ.json").write_text(json.dumps(quiz, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    facts = sum(1 for item in quiz["questions"] if item["kind"] == "fact")
    print(json.dumps({"document_words": len(document.split()), "tuples": len(graph["tuples"]),
                      "fact_questions": facts,
                      "absent_questions": len(quiz["questions"]) - facts,
                      "spread": args.spread, "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
