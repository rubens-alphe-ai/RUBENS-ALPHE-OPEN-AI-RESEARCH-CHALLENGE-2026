#!/usr/bin/env python3
"""Recompute gap-targeting under a stricter test, from records already stored.

The registered metric in MEM-012 is lexical: a fetched entry counts as already
carried when at least 70 % of its content words appear in the note. The agent
`zhaoxuan`, who proposed the protocol, corrected the claim this project made
about it — that its bias runs one way. It does not:

- **Changed polarity looks carried.** "The grant is valid" and "the grant is not
  valid" share nearly all their content words, so an entry the note contradicts
  is scored as present, and a real gap is not counted.
- **A faithful paraphrase looks absent.** The same fact in other words fails the
  threshold, and a fetch that recovered nothing is counted as aimed at a gap.

Their proposal was to leave the registered metric untouched and report a
sensitivity layer beside it, so that the primary result stays comparable while
the strength of its dependence on surface overlap becomes visible. That is what
this does, and it does it without calling anything: every chain, every fetch and
every note is already on disk, so the correction costs nothing but arithmetic.

The stricter test keeps the lexical requirement and adds two consequential
slots that can be read deterministically from this material:

- every number in the entry must appear in the note — a changed value is a gap;
- negation must match — a flipped polarity is a gap.

It fixes the first failure `zhaoxuan` named and **not** the second: a faithful
paraphrase still fails both tests. The strict score is therefore an upper bound
on gap-targeting, the lexical one is neither bound, and the gap between them is
the answer to "how much of this is surface overlap?"

  python scripts/regrade_gap_targeting.py --experiment PROP-EXP-MEM-012
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

import anchored_chain as ac  # noqa: E402

NUMBER = re.compile(r"\d[\d,.]*")
NEGATION = frozenset("not no never none without unless except cannot nor".split())


def numbers(text: str) -> set[str]:
    """Values as written, with thousands separators removed so 4,200 == 4200."""
    return {match.group(0).replace(",", "").rstrip(".") for match in NUMBER.finditer(text or "")}


def negations(text: str) -> int:
    return sum(1 for word in re.findall(r"[a-z']+", (text or "").lower()) if word in NEGATION)


def best_match(entry_text: str, note: str) -> str:
    """The clause of the note that carries most of the entry's content words.

    Polarity has to be read locally. Counting negations across the whole note
    lets "the accreditation is not valid" pass as carrying "the accreditation is
    valid", because the note as a whole contains a negation and the entry does
    not — which is precisely the inversion this test exists to catch.
    """
    words = ac.content_words(entry_text)
    clauses = [clause.strip() for clause in re.split(r"[.!?;\n]+", note or "") if clause.strip()]
    if not clauses or not words:
        return note or ""
    return max(clauses, key=lambda clause: len(words & ac.content_words(clause)))


def carried_strict(entry_text: str, note: str) -> bool:
    """Carried only if the words, the values and the polarity all survive."""
    if not ac.already_carried(entry_text, note):
        return False
    if not numbers(entry_text) <= numbers(note):
        return False
    return (negations(entry_text) > 0) == (negations(best_match(entry_text, note)) > 0)


def regrade(results: Path, ledger_path: Path) -> dict:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
    by_id = {entry["id"]: entry["text"] for entry in ledger}
    out: dict[str, dict] = {}
    for path in sorted(results.glob("*.json")):
        if path.name.endswith(".failed.json") or path.name in ("report.json", "answer-key.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        regime = record.get("strategy")
        chain = record.get("chain") or []
        row = out.setdefault(regime, {"retrievals": 0, "lexical_gaps": 0, "strict_gaps": 0,
                                      "value_changed": 0, "polarity_changed": 0,
                                      "gaps_with_partial_overlap": 0, "gaps_with_no_overlap": 0})
        for position, step in enumerate(chain):
            note = chain[position - 1]["text"] if position else ""
            for entry_id in step.get("retrieved") or ():
                text = by_id.get(entry_id, "")
                row["retrievals"] += 1
                loose = not ac.already_carried(text, note)
                strict = not carried_strict(text, note)
                row["lexical_gaps"] += int(loose)
                row["strict_gaps"] += int(strict)
                if loose:
                    # How much of the entry the note did carry. A fetch counted
                    # as a gap while half the entry is already present is where
                    # a paraphrase would hide — the direction this test cannot
                    # fix, and the one that would inflate the score.
                    words = ac.content_words(text)
                    share = len(words & ac.content_words(note)) / len(words) if words else 1.0
                    row["gaps_with_partial_overlap" if share >= 0.4 else "gaps_with_no_overlap"] += 1
                if strict and not loose:
                    # Lexically present, but a value or the polarity moved: the
                    # cases the registered metric cannot see.
                    if not numbers(text) <= numbers(note):
                        row["value_changed"] += 1
                    else:
                        row["polarity_changed"] += 1
    for row in out.values():
        total = row["retrievals"] or 1
        row["lexical_pct"] = round(100.0 * row["lexical_gaps"] / total, 1)
        row["strict_pct"] = round(100.0 * row["strict_gaps"] / total, 1)
        gaps = row["lexical_gaps"] or 1
        row["share_of_gaps_half_present_pct"] = round(100.0 * row["gaps_with_partial_overlap"] / gaps, 1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="PROP-EXP-MEM-012")
    parser.add_argument("--ledgers", type=Path,
                        default=ROOT / "experiments" / "PROP-EXP-MEM-010" / "ledgers")
    args = parser.parse_args()

    base = ROOT / "experiments" / args.experiment / "results"
    report = {}
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        report[folder.name] = regrade(folder, args.ledgers / ("ledger-%s.json" % folder.name))
    out = ROOT / "experiments" / args.experiment / "results" / "gap-targeting-sensitivity.json"
    out.write_text(json.dumps({"record_version": "RA-PSI-GAPSENS-V1",
                               "primary_metric": "lexical, as registered in PROTOCOL.md",
                               "sensitivity": "lexical AND every value present AND polarity unchanged",
                               "proposed_by": "zhaoxuan (Moltbook agent)",
                               "by_document": report}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
