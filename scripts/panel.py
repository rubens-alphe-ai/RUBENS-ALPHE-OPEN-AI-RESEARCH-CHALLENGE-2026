#!/usr/bin/env python3
"""A public reader panel: many independent readers, none of them paid, none trusted.

Every number this project publishes depends on a reader — a model that sees only
a handoff and answers a frozen quiz. That is the confound named in every result
file: a stronger reader extracts facts a weaker one misses, so "facts kept" is
partly a property of the reader. Two readers were compared. Two is not enough,
and no budget here buys ten unrelated model families.

An audience of agents is ten unrelated model families, for nothing. What it is
not is a set of participants who should have to trust us, or whom we should have
to trust. So the panel is sealed:

1. `seal` renders the quiz with a **secret nonce**, writes the key and the nonce
   to a private folder, and publishes only the handoff, the rendered questions,
   and the SHA-256 of the key, of the nonce and of the quiz file.
2. Agents answer in public, one letter per question.
3. `reveal` publishes the nonce and the quiz. Anyone re-runs `render_quiz` with
   that nonce, obtains the same rendering byte for byte, recomputes the key, and
   checks it against the hash published before any answer arrived.

Neither side can move afterwards. We cannot fit a key to the answers, because
the key was hashed first. A responder cannot look the answers up, because the
quiz stays sealed until every answer is in.

  python scripts/panel.py seal --quiz Q.json --handoff h.txt --out panel/ --private ~/.ra-psi/panel
  python scripts/panel.py grade --panel panel/ --private ~/.ra-psi/panel --answers replies/
  python scripts/panel.py reveal --panel panel/ --private ~/.ra-psi/panel
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402
from evaluate_experiment import sha256_text  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


LINE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,3}[0-9]{1,3})[^A-Za-z0-9]{0,6}([A-Ea-e])(?![A-Za-z0-9])")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_letters(raw: str, ids: list[str]) -> tuple[dict[str, str], list[str]]:
    """One letter per question id, read from whatever a responder actually wrote.

    The experiments' reader is a script and is asked for JSON. A panel responder
    is an agent writing a comment, and will write `Q01 A` or `Q01: A` or
    `Q01 - (A)`. Demanding JSON from a volunteer is a good way to collect
    nothing, so this reads lines; a JSON reply still works, because the same
    pattern matches inside it.

    Identifiers are not all `Q`: the quiz builder names absent-fact questions
    `X01` and up, and those are the ones that measure invention. Matching only
    `Q` would have silently dropped exactly the answers that matter most.
    """
    found: dict[str, str] = {}
    for question_id, letter in LINE.findall(raw or ""):
        found.setdefault(question_id.upper(), letter.upper())
    answers = {qid: found[qid] for qid in ids if qid in found}
    missing = [qid for qid in ids if qid not in found]
    return answers, (["missing: " + ", ".join(missing)] if missing else [])


def render_public(handoff: str, rendered: list[dict]) -> str:
    """Exactly what a reader sees, and nothing that would give the answer away."""
    # The count comes from the rendering, never from a number typed here: the
    # quiz builder drops any question whose support it cannot verify, so how
    # many survive is not known until it has run.
    count = len(rendered)
    last = rendered[-1]["id"] if rendered else "Q01"
    lines = ["# Reader panel: answer from the note alone", "",
             "Below is a handover note, then %d questions about the project it describes." % count,
             "You have not seen that project and you will not be shown it.",
             "",
             "Answer every question with one letter. Where the note does not contain the",
             "answer, the honest choice is the option that says so — it is a real option",
             "on every question, and choosing it is never penalised. Guessing is.",
             "",
             "Reply with %d lines, one per question, like `%s B`. Use the identifier"
             % (count, rendered[0]["id"] if rendered else "Q01"),
             "printed with each question — they are not all numbered the same way, and the",
             "last one is `%s`. Nothing else in the reply." % last,
             "", "## The note", "", handoff.strip(), "", "## The questions", ""]
    for item in rendered:
        lines.append("**%s** %s" % (item["id"], item["question"]))
        for letter, option in item["options"].items():
            lines.append("- %s) %s" % (letter, option))
        lines.append("")
    return "\n".join(lines) + "\n"


def seal(args: argparse.Namespace) -> dict:
    quiz_text = args.quiz.read_text(encoding="utf-8")
    quiz = json.loads(quiz_text)
    handoff = args.handoff.read_text(encoding="utf-8")
    nonce = args.nonce or secrets.token_hex(16)
    rendered, key = hq.render_quiz(quiz, nonce)

    args.private.expanduser().mkdir(parents=True, exist_ok=True)
    (args.private.expanduser() / "panel-secret.json").write_text(
        json.dumps({"nonce": nonce, "key": key, "quiz_file": str(args.quiz), "sealed_at_utc": now()},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "PANEL.md").write_text(render_public(handoff, rendered), encoding="utf-8")
    commitment = {"record_version": "RA-PSI-PANEL-V1", "sealed_at_utc": now(),
                  "handoff_sha256": sha256_text(handoff),
                  "rendered_sha256": sha256_text(json.dumps(rendered, ensure_ascii=False, sort_keys=True)),
                  "key_sha256": sha256_text(json.dumps(key, ensure_ascii=False, sort_keys=True)),
                  "nonce_sha256": sha256_text(nonce),
                  "quiz_sha256": sha256_text(quiz_text),
                  "questions": len(rendered),
                  "how_to_verify": ("After the reveal: render_quiz(QUIZ.json, nonce) reproduces the rendering "
                                    "and the key, and their hashes must equal the ones above, which were "
                                    "published before any answer arrived.")}
    (args.out / "commitment.json").write_text(json.dumps(commitment, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    # The rendering is published so a responder can check that the questions they
    # answered are the ones being graded; it carries no key.
    (args.out / "rendered.json").write_text(json.dumps(rendered, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    return commitment


def grade(args: argparse.Namespace) -> dict:
    secret = json.loads((args.private.expanduser() / "panel-secret.json").read_text(encoding="utf-8"))
    rendered = json.loads((args.panel / "rendered.json").read_text(encoding="utf-8"))
    key = secret["key"]
    rows = []
    for path in sorted(args.answers.glob("*.json")):
        submission = json.loads(path.read_text(encoding="utf-8"))
        ids = [item["id"] for item in rendered]
        if "answers_text" in submission:
            answers, problems = read_letters(submission["answers_text"], ids)
        else:
            answers = {qid: str(letter).upper() for qid, letter in (submission.get("answers") or {}).items()}
            problems = []
        if not answers:
            rows.append({"responder": submission.get("responder", path.stem), "error": "no usable answer"})
            continue
        rows.append({"responder": submission.get("responder", path.stem),
                     "model_family": submission.get("model_family"),
                     "problems": problems, **hq.grade(answers, key, rendered)})
    scored = [row for row in rows if "fact_accuracy" in row]
    summary = {"responders": len(scored), "unusable": len(rows) - len(scored)}
    if scored:
        values = [100.0 * row["fact_accuracy"] for row in scored]
        summary.update({"facts_kept_pct_min": round(min(values), 1),
                        "facts_kept_pct_max": round(max(values), 1),
                        "spread_pp": round(max(values) - min(values), 1),
                        "inventions_total": sum(row["inventions"] for row in scored)})
    return {"summary": summary, "responders": rows}


def reveal(args: argparse.Namespace) -> dict:
    secret = json.loads((args.private.expanduser() / "panel-secret.json").read_text(encoding="utf-8"))
    commitment = json.loads((args.panel / "commitment.json").read_text(encoding="utf-8"))
    checks = {"nonce_matches_commitment": sha256_text(secret["nonce"]) == commitment["nonce_sha256"],
              "key_matches_commitment":
                  sha256_text(json.dumps(secret["key"], ensure_ascii=False, sort_keys=True)) == commitment["key_sha256"]}
    payload = {"record_version": "RA-PSI-PANEL-REVEAL-V1", "revealed_at_utc": now(),
               "nonce": secret["nonce"], "key": secret["key"], "checks": checks,
               "commitment": commitment}
    if not all(checks.values()):
        # Refusing to publish a reveal that does not match its own commitment is
        # the only part of this that has to be right.
        raise SystemExit("reveal does not match the commitment: " + json.dumps(checks))
    (args.panel / "reveal.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("seal", "grade", "reveal"))
    parser.add_argument("--quiz", type=Path)
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--panel", type=Path, default=ROOT / "experiments" / "PANEL-2026-09" / "public")
    parser.add_argument("--out", type=Path, default=ROOT / "experiments" / "PANEL-2026-09" / "public")
    parser.add_argument("--answers", type=Path, default=ROOT / "experiments" / "PANEL-2026-09" / "answers")
    parser.add_argument("--private", type=Path, default=Path("~/.ra-psi/panel"))
    parser.add_argument("--nonce", help="only for reproducing a seal; normally generated")
    args = parser.parse_args()

    if args.action == "seal":
        if not (args.quiz and args.handoff):
            raise SystemExit("seal needs --quiz and --handoff")
        print(json.dumps(seal(args), indent=2, ensure_ascii=False))
    elif args.action == "grade":
        print(json.dumps(grade(args), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(reveal(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
