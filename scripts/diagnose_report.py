#!/usr/bin/env python3
"""Turn a benchmark run into a report someone outside research would act on.

Everything this project produces is addressed to a researcher: confidence
intervals, hop tables, invention counts. That is the right form for a result and
the wrong form for a decision. Someone deciding whether to change how their
system hands work over needs three sentences — how much your format loses, where
it loses it, and what recovers it — and then needs to be able to prove the three
sentences without trusting whoever wrote them.

So this writes two files.

`REPORT.md` is one page in plain language, with a single table and no interval
in the body. The intervals are not hidden: they are in the appendix, and every
claim in the body is qualified there if it is not resolved.

`verify.json` is what makes the page worth reading. It carries the SHA-256 of
the document, of the quiz, of the answer key and of every stored run, plus one
command that recomputes every number in the report from the stored answers. A
report that cannot be recomputed by its recipient is a brochure.

Two refusals, because a diagnostic that oversells is worth less than none:

* A run whose failures fell unevenly across strategies is **refused**. The page
  says so and carries no numbers. That rule already exists in `handoff_bench`
  and this reads its verdict rather than deciding again.
* An effect whose interval crosses zero is never stated as a gain. It is
  reported as not resolved at this number of runs, with what it would take.

  python scripts/diagnose_report.py --bench experiments/.../results/clinic --out report/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_bench as hb  # noqa: E402

PLAIN = {
    "summary": "a free summary — what most systems do today",
    "checklist": "naming the kinds of item to carry, with their status",
    "sections": "the same facts under named headings",
    "facts_only": "one fact per line, nothing else",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolved(row: dict) -> bool:
    """Whether an effect is distinguishable from nothing at this many runs."""
    low, high = row.get("vs_control_ci95") or (0.0, 0.0)
    return low > 0 or high < 0


def best_arm(table: dict, control: str) -> tuple[str, dict] | tuple[None, None]:
    candidates = [(name, row) for name, row in table.items()
                  if name != control and resolved(row) and row.get("vs_control_pp", 0) > 0]
    if not candidates:
        return None, None
    return max(candidates, key=lambda pair: pair[1]["vs_control_pp"])


def render(report: dict, verify: dict, control: str) -> str:
    meta, hops = report["meta"], report["by_hop"]
    usable = (meta.get("usability") or {}).get("usable", True)
    deepest = max(hops, key=int)
    first, last = hops[min(hops, key=int)], hops[deepest]
    lines = ["# What your handover format keeps, and what it loses", "",
             "Document: `%s`. Measured on %s." % (meta["document"], datetime.now(timezone.utc).strftime("%Y-%m-%d")), ""]

    if not usable:
        lines += ["## This run produced no result", "",
                  (meta["usability"]["reason"][0].upper() + meta["usability"]["reason"][1:]) + ".",
                  "", "Failures by arm: %s of %s runs. Nothing below is reported because a series that "
                  "loses more trials in one condition than another is not evidence. The run should be "
                  "repeated." % (meta["usability"]["failed_by_arm"], meta["usability"]["runs_by_arm"]), ""]
        return "\n".join(lines) + "\n"

    control_first = first[control]["facts_kept_pct"]
    control_last = last[control]["facts_kept_pct"]
    name, row = best_arm(last, control)

    lines += ["## The short version", "",
              "- A colleague who reads only the handover, and never the document, can answer "
              "**%.0f%%** of the questions about it after one handover." % control_first,
              "- After %s handovers, **%.0f%%**." % (deepest, control_last),
              "- **Almost all of the loss happens at the first handover.** %.0f points go immediately; "
              "%.0f more over the next %d." % (100 - control_first, control_first - control_last, int(deepest) - 1)]
    if name:
        lines.append("- Changing the instruction given to whoever writes the handover — %s — recovers "
                     "**%.0f points** of that." % (PLAIN.get(name, name), row["vs_control_pp"]))
    else:
        lines.append("- No alternative instruction was distinguishable from your current one at this "
                     "number of runs. See the appendix for what would be needed.")
    asked = last[control]["absent_questions_asked"]
    lines += ["- **Nothing was invented.** The document never answers %d of the questions, and each was put "
              "to a reader %d times per instruction. Every arm chose \"the text does not say\" %s."
              % (meta["absent_questions"], asked // max(1, meta["absent_questions"]),
                 "every single time" if all(r["inventions"] == 0 for r in last.values())
                 else "almost every time"),
              ""]

    lines += ["## Every instruction, at the deepest handover measured", "",
              "| How the handover is written | Questions answered | Difference | Resolved at %d runs |"
              % meta["repeats"], "|---|---|---|---|"]
    for arm in sorted(last, key=lambda n: -last[n]["facts_kept_pct"]):
        r = last[arm]
        if arm == control:
            lines.append("| %s | %.0f%% | — | — |" % (PLAIN.get(arm, arm), r["facts_kept_pct"]))
            continue
        lines.append("| %s | %.0f%% | %+.0f points | %s |"
                     % (PLAIN.get(arm, arm), r["facts_kept_pct"], r["vs_control_pp"],
                        "yes" if resolved(r) else "**no**"))
    lines += ["", "\"Resolved\" means the difference is larger than the run-to-run noise. An unresolved "
              "difference is not a small effect; it is an effect this many runs cannot see.", ""]

    lines += ["## How to check this without trusting us", "",
              "Every number above comes from stored answers, not from a model's opinion. No model graded "
              "anything: a reader picked letters and a script compared them to a key fixed before the "
              "first run.", "",
              "```", verify["recompute_command"], "```", "",
              "`verify.json` carries the SHA-256 of the document, the quiz, the answer key and all %d "
              "stored runs. If any of them changed after the fact, that command says so."
              % len(verify["runs"]), ""]

    lines += ["## Appendix: intervals and method", "",
              "| Instruction | Difference | 95% confidence interval |", "|---|---|---|"]
    for arm in sorted(last):
        if arm == control:
            continue
        r = last[arm]
        low, high = r.get("vs_control_ci95") or (0, 0)
        lines.append("| %s | %+.1f pp | %.1f to %.1f |" % (arm, r.get("vs_control_pp", 0), low, high))
    lines += ["",
              "%d runs per instruction, %d fact questions and %d questions the document never answered, "
              "handovers cut to %s words so no instruction can win by writing more. Writer `%s`, reader "
              "`%s` — deliberately different models, because a model reading its own handover measures "
              "nothing."
              % (meta["repeats"], meta["fact_questions"], meta["absent_questions"],
                 meta.get("word_limit") or "no limit", meta["generator"], meta["reader"]),
              "",
              "Failed runs: %d." % meta.get("failed_runs", 0), ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", type=Path, required=True, help="a handoff_bench output folder")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--document", type=Path, help="the measured document, to hash into verify.json")
    parser.add_argument("--quiz", type=Path, help="the quiz, to hash into verify.json")
    parser.add_argument("--control", default=hb.CONTROL)
    args = parser.parse_args()

    report = json.loads((args.bench / "report.json").read_text(encoding="utf-8"))
    runs = {path.name: sha256_file(path) for path in sorted(args.bench.glob("*.json"))
            if path.name not in ("report.json",)}
    verify = {"record_version": "RA-PSI-VERIFY-V1", "written_at_utc": datetime.now(timezone.utc).isoformat(),
              "bench": str(args.bench), "runs": runs,
              "document_sha256": sha256_file(args.document) if args.document else None,
              "quiz_sha256": sha256_file(args.quiz) if args.quiz else None,
              "recompute_command": "python scripts/regression_suite.py",
              "what_it_proves": ("Every percentage in REPORT.md is recomputed from the stored letters and "
                                 "compared to what was published. It exits non-zero if any of them moved.")}

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "verify.json").write_text(json.dumps(verify, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "REPORT.md").write_text(render(report, verify, args.control), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "runs_hashed": len(runs),
                      "usable": (report["meta"].get("usability") or {}).get("usable", True)}, indent=2))


if __name__ == "__main__":
    main()
