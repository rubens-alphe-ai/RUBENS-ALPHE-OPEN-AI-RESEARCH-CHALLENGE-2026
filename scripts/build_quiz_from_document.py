#!/usr/bin/env python3
"""Turn any document into a handoff quiz, and refuse the questions it cannot verify.

Until now the measurement only worked on one document, the project's own state,
because its 42 questions were written by hand. That is a research demo, not a
method: nobody can measure their own handoffs with it.

This builds the quiz from a document, and — this is the part that matters —
checks every question mechanically before keeping it:

* **fact questions**: the model must quote the span of the document that
  supports the answer. The quote must appear in the document verbatim, and the
  answer's key words must appear inside that quote. A question whose support
  cannot be found is dropped, not trusted.
* **distractors**: each wrong option must not appear in the document, so a wrong
  option can never be accidentally true.
* **absent questions**: the model proposes questions the document does not
  answer. Each is put back to a second, independent reader with the whole
  document and the instruction to answer it or say it is absent. Any question
  that reader can answer is dropped: it was not absent.

What comes out is the same `QUIZ.json` format the rest of the pipeline already
uses, so any document can now be measured with the published method.

Example:
  python scripts/build_quiz_from_document.py --document notes.md \\
      --config ~/.ra-psi/run-config.json --out quiz.json --facts 32 --absent 10
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

from evaluate_experiment import AdapterError, call  # noqa: E402
from ingest_scorecards import read_evaluator_json  # noqa: E402

WRITER = """You are preparing a reading test about the document below.

Write {count} questions about facts the document states explicitly. Each question
must have exactly one correct answer, three wrong options, and a verbatim quote
from the document that supports the correct answer.

Rules:
- quote the document exactly, copy and paste, 5 to 40 words;
- the correct answer must be contained in, or directly stated by, that quote;
- wrong options must be plausible but must NOT appear in the document;
- no question about the document's layout, length or wording; ask about content;
- no two questions about the same fact.

Return ONE JSON object and nothing else:
{{"questions": [{{"question": "...", "correct": "...", "distractors": ["...", "...", "..."], "quote": "..."}}]}}

=== DOCUMENT ===
{document}
=== END ===
"""

ABSENT = """Below is a document.

Write {count} questions that a reader might reasonably ask about this subject and
that the document does NOT answer. They must be about the same subject, not
about unrelated topics, and each must have four plausible but unsupported
options.

Return ONE JSON object and nothing else:
{{"questions": [{{"question": "...", "distractors": ["...", "...", "...", "..."]}}]}}

=== DOCUMENT ===
{document}
=== END ===
"""

CHECK = """Answer using only the document below.

Question: {question}

If the document states the answer, reply with the JSON object
{{"answerable": true, "quote": "the sentence that answers it"}}.
If it does not, reply with {{"answerable": false}}.
Reply with one JSON object and nothing else.

=== DOCUMENT ===
{document}
=== END ===
"""

NOT_STATED = "The text does not say."


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def keywords(text: str) -> list[str]:
    return [word for word in re.findall(r"[\w'-]+", text.lower()) if len(word) > 3]


def supported(document: str, quote: str, answer: str) -> bool:
    """The quote must be in the document, and the answer must be in the quote."""
    flat, quoted = normalise(document), normalise(quote)
    if len(quoted) < 20 or quoted not in flat:
        return False
    words = keywords(answer)
    if not words:
        return False
    hits = sum(1 for word in words if word in quoted)
    return hits >= max(1, len(words) // 2)


def unsupported(document: str, distractors: list[str]) -> bool:
    """No wrong option may appear in the document, or it might be true."""
    flat = normalise(document)
    return all(normalise(option) and normalise(option) not in flat for option in distractors)


def ask(entry: dict, prompt: str, max_tokens: int) -> dict:
    content, _ = call(entry, prompt, max_tokens)
    path = Path(ROOT / "docs" / ".quiz-builder-last.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return read_evaluator_json(path)


def build(document: str, writer: dict, checker: dict, facts: int, absent: int, max_tokens: int) -> dict:
    report = {"asked_for": {"facts": facts, "absent": absent}, "dropped": []}
    kept: list[dict] = []
    raw = ask(writer, WRITER.format(count=facts + max(4, facts // 3), document=document), max_tokens)
    for index, item in enumerate(raw.get("questions", []), start=1):
        question, correct = str(item.get("question", "")).strip(), str(item.get("correct", "")).strip()
        distractors = [str(option).strip() for option in item.get("distractors", [])][:3]
        quote = str(item.get("quote", ""))
        if not question or not correct or len(distractors) != 3:
            report["dropped"].append({"question": question[:80], "why": "incomplete"})
        elif not supported(document, quote, correct):
            report["dropped"].append({"question": question[:80], "why": "quote not found in the document"})
        elif not unsupported(document, distractors):
            report["dropped"].append({"question": question[:80], "why": "a wrong option appears in the document"})
        elif len(kept) < facts:
            kept.append({"id": "Q%02d" % (len(kept) + 1), "kind": "fact", "question": question,
                         "correct": correct, "distractors": distractors, "support": quote})

    kept_absent: list[dict] = []
    raw = ask(writer, ABSENT.format(count=absent + max(4, absent), document=document), max_tokens)
    for item in raw.get("questions", []):
        question = str(item.get("question", "")).strip()
        distractors = [str(option).strip() for option in item.get("distractors", [])][:4]
        if not question or len(distractors) != 4:
            report["dropped"].append({"question": question[:80], "why": "incomplete"})
            continue
        if not unsupported(document, distractors):
            # An option the document contains could be defended as true, and a
            # reader choosing it would be counted as inventing for no reason.
            report["dropped"].append({"question": question[:80], "why": "an option appears in the document"})
            continue
        if len(kept_absent) >= absent:
            break
        try:
            verdict = ask(checker, CHECK.format(question=question, document=document), max_tokens)
        except (AdapterError, SystemExit) as exc:
            report["dropped"].append({"question": question[:80], "why": "checker failed: %s" % str(exc)[:60]})
            continue
        if verdict.get("answerable"):
            report["dropped"].append({"question": question[:80], "why": "the document does answer it"})
            continue
        kept_absent.append({"id": "X%02d" % (len(kept_absent) + 1), "kind": "absent",
                            "question": question, "distractors": distractors})

    quiz = {"quiz_version": "RA-PSI-DOCUMENT-QUIZ-V1", "not_stated_option": NOT_STATED,
            "source": "Generated from a document and mechanically verified: every fact question keeps a verbatim "
                      "supporting quote, no wrong option appears in the document, and every absent question was "
                      "confirmed unanswerable by a second model reading the whole document.",
            "questions": kept + kept_absent}
    report.update(kept_facts=len(kept), kept_absent=len(kept_absent), dropped_count=len(report["dropped"]))
    return {"quiz": quiz, "report": report}


def entry_from(private: dict, name: str, model: str, endpoint: str, key: str, max_tokens: int) -> dict:
    location = private.get("keys", {}).get(key)
    if not location:
        raise SystemExit("no key location configured for %r" % key)
    # Writers that reason by default spend the whole budget thinking and return
    # nothing; the quiz builder only needs an answer.
    entry = {"evaluator_id": name, "provider": key, "model": model, "endpoint": endpoint,
             "json_mode": False, "max_tokens": max_tokens, "extra_body": {"reasoning": {"effort": "minimal"}}}
    entry.update({k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")})
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--facts", type=int, default=32)
    parser.add_argument("--absent", type=int, default=10)
    parser.add_argument("--writer-model", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--checker-model", default="openai/gpt-oss-120b")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--max-tokens", type=int, default=8000)
    args = parser.parse_args()

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    document = args.document.read_text(encoding="utf-8")
    writer = entry_from(private, "quiz-writer", args.writer_model, args.endpoint, args.key, args.max_tokens)
    checker = entry_from(private, "quiz-checker", args.checker_model, args.endpoint, args.key, args.max_tokens)
    built = build(document, writer, checker, args.facts, args.absent, args.max_tokens)
    args.out.write_text(json.dumps(built["quiz"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(args.out), **built["report"]}, indent=2, ensure_ascii=False)[:2000])
    raise SystemExit(0 if built["report"]["kept_facts"] >= max(8, args.facts // 2) else 1)


if __name__ == "__main__":
    main()
