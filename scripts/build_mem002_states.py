#!/usr/bin/env python3
"""Generate the two PROP-EXP-MEM-002 input states from one canonical fact list.

PROP-EXP-MEM-001 compared two hand-written states that did not carry the same
facts, so its score gap measured content rather than structure, and its
structured state leaked its own condition label into the outputs (see
experiments/PROP-EXP-MEM-001/PILOT_DESIGN_FLAWS.md).

Here both states are rendered from ``facts.json``:

* ``STATE_A.txt`` is continuous prose, one paragraph per theme, no headings;
* ``STATE_B.json`` groups the same items into named sections.

Every fact and its status phrase appear verbatim in both, so the only variable
is structure. The files are named A and B, not flat and structured, because a
name is exactly the kind of label that leaked last time; the mapping lives in
the experiment manifest, not in anything a generator reads.

The script refuses to write anything unless the equivalence check passes and
neither state contains a condition-identifying string. It also records the
tokens that exist only in STATE_B (its section keys), so blinded outputs can
later be scanned for them.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "PROP-EXP-MEM-002"

# Case-sensitive labels that would identify a condition if they reached a
# generator. The project's own prose legitimately says "flat baseline" and
# "structured memory" in both states, so lowercase descriptions are allowed.
FORBIDDEN_IN_STATES = (
    '"condition"',
    "STRUCTURED_MEMORY",
    "BASELINE_STATE",
    "STATE_A",
    "STATE_B",
    "PROP-EXP-MEM-002",
)


def status_clause(phrase: str) -> str:
    return "(Status: %s.)" % phrase


def render_prose(facts: dict) -> str:
    phrases = facts["status_phrases"]
    paragraphs = [
        "Project: %s." % facts["project"],
        "Mission: %s" % facts["mission"],
    ]
    for section in facts["sections"]:
        sentences = [
            "%s %s" % (item["text"], status_clause(phrases[item["status"]]))
            for item in section["items"]
        ]
        paragraphs.append(" ".join(sentences))
    return "\n\n".join(paragraphs) + "\n"


def render_structured(facts: dict) -> dict:
    phrases = facts["status_phrases"]
    state = {"project": facts["project"], "mission": facts["mission"]}
    for section in facts["sections"]:
        state[section["key"]] = [
            {"text": item["text"], "status": phrases[item["status"]]}
            for item in section["items"]
        ]
    return state


def check_equivalence(facts: dict, prose: str, structured: dict) -> list:
    problems = []
    phrases = facts["status_phrases"]
    structured_items = {
        (entry["text"], entry["status"])
        for key, value in structured.items()
        if isinstance(value, list)
        for entry in value
    }
    for field in ("project", "mission"):
        if facts[field] not in prose:
            problems.append("prose is missing the %s" % field)
        if structured.get(field) != facts[field]:
            problems.append("structured state is missing the %s" % field)
    for section in facts["sections"]:
        for item in section["items"]:
            phrase = phrases[item["status"]]
            if "%s %s" % (item["text"], status_clause(phrase)) not in prose:
                problems.append("prose lacks fact or status: %.60s" % item["text"])
            if (item["text"], phrase) not in structured_items:
                problems.append("structured state lacks fact or status: %.60s" % item["text"])
    expected = sum(len(section["items"]) for section in facts["sections"])
    if len(structured_items) != expected:
        problems.append(
            "structured state has %d items, fact list has %d" % (len(structured_items), expected)
        )
    return problems


def check_labels(name: str, text: str) -> list:
    return [
        "%s contains forbidden label %r" % (name, label)
        for label in FORBIDDEN_IN_STATES
        if label in text
    ]


def main() -> None:
    facts = json.loads((EXPERIMENT / "facts.json").read_text(encoding="utf-8"))
    prose = render_prose(facts)
    structured = render_structured(facts)
    structured_text = json.dumps(structured, indent=2, ensure_ascii=False) + "\n"

    problems = check_equivalence(facts, prose, structured)
    problems += check_labels("STATE_A", prose)
    problems += check_labels("STATE_B", structured_text)
    if problems:
        print("REFUSED: nothing written")
        print("\n".join(" - " + problem for problem in problems))
        sys.exit(1)

    (EXPERIMENT / "STATE_A.txt").write_text(prose, encoding="utf-8")
    (EXPERIMENT / "STATE_B.json").write_text(structured_text, encoding="utf-8")

    # Tokens a generator could only have copied from STATE_B. Section keys are
    # the obvious ones; if one appears in a blinded output, the evaluator could
    # tell which state produced it.
    only_in_b = sorted(
        key for key in structured if key not in ("project", "mission") and key not in prose
    )
    (EXPERIMENT / "leak_markers.json").write_text(
        json.dumps(
            {
                "purpose": "strings that appear only in one input state and would reveal the condition if found in an output",
                "only_in_STATE_B": only_in_b,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "facts": sum(len(section["items"]) for section in facts["sections"]),
        "equivalence": "PASS",
        "labels": "PASS",
        "STATE_A.txt": {
            "chars": len(prose),
            "sha256": hashlib.sha256(prose.encode("utf-8")).hexdigest(),
        },
        "STATE_B.json": {
            "chars": len(structured_text),
            "sha256": hashlib.sha256(structured_text.encode("utf-8")).hexdigest(),
        },
        "leak_markers": only_in_b,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
