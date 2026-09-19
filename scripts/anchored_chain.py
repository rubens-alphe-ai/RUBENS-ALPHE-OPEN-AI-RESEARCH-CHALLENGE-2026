#!/usr/bin/env python3
"""Memory against archive: what a chain keeps when it can check something.

Stage 2 of the Continuity Programme. MEM-008 showed that a chain of handoffs
loses almost everything it will lose at the *first* handoff, then transmits the
remainder nearly intact. That is the behaviour of a memory. The question here is
whether a chain that can consult a verifiable archive loses differently — not
more slowly, but recoverably.

Three regimes, same writer, same instruction, same word budget, same quiz:

- **bare** — each writer sees only the previous handoff. This is MEM-008's
  condition and the control.
- **index** — each writer also sees the archive's index: every entry's id and a
  six-word label, never its content. It can see that something exists which its
  note no longer mentions, and nothing more. This arm exists to separate
  *knowing what was lost* from *getting it back*; without it, any effect of the
  archive would be uninterpretable.
- **anchored** — the writer sees the index, names up to `--fetch` entries, and
  receives exactly those, verbatim and hash-checked, before writing.
- **coverage** — coverage inversion. The writer first maps what its note already
  carries, *before* being shown the index; then it marks every index entry as
  covered, uncertain or absent against that map, and its fetches are spent on
  the gaps first, an order this script enforces rather than requests. Proposed
  by the agent `zhaoxuan` on Moltbook in reply to MEM-011, and registered as
  PROP-EXP-MEM-012 before it ran.

The archive is built by `scripts/build_ledger.py` without calling a model, so it
cannot leak the quiz: it is the document itself, cut into hashed sentences.

The retrieval channel is deliberately narrow. Handing the whole archive back
would test nothing but whether a model can copy. What is being measured is
whether a chain can *choose* what to recover — and the ids it asks for are
recorded at every hop, because that choice is the finding whether or not the
threshold is met.

Example:
  python scripts/anchored_chain.py --document experiments/PROP-EXP-MEM-010/documents/clinic.md \\
      --quiz experiments/PROP-EXP-MEM-010/quiz-clinic.json --ledger .../ledger-clinic.json \\
      --config ~/.ra-psi/run-config.json --out .../results/clinic --repeats 6 --read-at 1 3 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import build_ledger as bl  # noqa: E402
import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402
from evaluate_experiment import AdapterError, call, sha256_text  # noqa: E402

CONTROL = "bare"
REGIMES = ("bare", "index", "anchored", "coverage")
ID = re.compile(r"\bE\d{1,3}\b", re.IGNORECASE)
MARK = re.compile(r"\b(E\d{1,3})\b\s*[:\-—]?\s*(covered|uncertain|absent)\b", re.IGNORECASE)
STOP = frozenset("a an and are as at be by for from has have in is it its of on or that the to was were with".split())

INDEX_NOTE = """An archive of the original document exists. You cannot read it. This is its
index: one line per entry, with an identifier and the first few words only.

{index}

Use it to notice what your note above no longer carries. Where an entry's subject
is missing from your note, say so explicitly as a gap, with its identifier. Do not
guess what an entry contains.

"""

ASK = """Below is a handover note. It has passed through several hands and has lost
content. An archive of the original document exists; this is its index, one line
per entry, identifier and first few words only:

{index}

=== THE NOTE ===
{note}
=== END ===

Name the {limit} entries whose content would most improve the note: the ones whose
subject is missing or vague, and that you cannot reconstruct from the note alone.
Answer with identifiers only, separated by commas. Nothing else.
"""

RETRIEVED = """You also retrieved these entries from the archive. They are verbatim from the
original document and have been checked against their recorded hashes:

{entries}

"""


COVERAGE = """Below is a handover note. Before you are shown anything else, write down what it
already carries, grouped under these headings, one short line each:

CLAIMS, ENTITIES, CAUSAL TRANSITIONS, EXCEPTIONS, TERMINAL OUTCOMES.

Include only what is in the note. Do not speculate about what is missing yet.

=== THE NOTE ===
{note}
=== END ===
"""

INVERT = """This is your own coverage map of a handover note:

{map}

An archive of the original document exists. Below is its index: one line per
entry, an identifier and the first few words, with the digits hidden. You cannot
read the entries.

{index}

Mark every identifier as covered, uncertain or absent with respect to your
coverage map, one per line, in the form `E01 covered`. Write `covered` only
where you can point to the span of the note that carries it, and quote that span
after the word. Then, on a final line beginning `FETCH:`, name the {limit}
identifiers you want, absent ones first, then uncertain. Do not name an
identifier you marked covered.
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_marks(text: str) -> dict[str, str]:
    """Which identifiers the writer says its note already carries."""
    marks: dict[str, str] = {}
    for entry_id, state in MARK.findall(text or ""):
        marks.setdefault(entry_id.upper(), state.lower())
    return marks


def order_by_gap(ids: list[str], marks: dict[str, str]) -> list[str]:
    """Absent first, then uncertain, then anything else, order kept within each.

    The protocol is enforced here rather than requested in the prompt: a rule a
    model may quietly ignore is not a condition an experiment can claim to have
    tested.
    """
    rank = {"absent": 0, "uncertain": 1}
    return sorted(ids, key=lambda entry_id: rank.get(marks.get(entry_id, ""), 2))


def content_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", (text or "").lower()) if word not in STOP}


def already_carried(entry_text: str, note: str, share: float = 0.7) -> bool:
    """Whether a fetched entry was, by this test, already recoverable from the note.

    A crude, deterministic proxy: an entry counts as already carried when at
    least `share` of its content words appear in the note. It cannot tell a
    changed number from a kept one, so it will overcount entries as carried. It
    is stated in advance, applied identically to every arm, and reported as a
    proxy rather than as a measurement of meaning.
    """
    words = content_words(entry_text)
    if not words:
        return True
    return len(words & content_words(note)) / len(words) >= share


def fetch_line(text: str) -> str:
    """What follows the last `FETCH:` marker, or nothing if there is none.

    No marker means no request: silently falling back to the whole reply would
    turn a writer that refused to choose into one that fetched the first four
    entries it had listed.
    """
    parts = re.split(r"FETCH\s*:", text or "", flags=re.IGNORECASE)
    return parts[-1] if len(parts) > 1 else ""


def parse_ids(text: str, limit: int) -> list[str]:
    """Identifiers the writer asked for, in order, de-duplicated."""
    seen: list[str] = []
    for match in ID.findall(text or ""):
        upper = match.upper()
        if upper not in seen:
            seen.append(upper)
        if len(seen) >= limit:
            break
    return seen


def render_entries(entries: list[dict]) -> str:
    return "\n".join("%s  %s" % (entry["id"], entry["text"]) for entry in entries)


def write_hop(regime: str, entry: dict, note: str, instruction: str, ledger: list[dict],
              index_text: str, fetch_limit: int, max_tokens: int, attempts: int = 2) -> dict:
    """One handoff, under one regime. Returns the text and what was consulted."""
    asked: list[str] = []
    got: list[str] = []
    marks: dict[str, str] = {}
    preamble = ""
    if regime == "index":
        preamble = INDEX_NOTE.format(index=index_text)
    elif regime in ("anchored", "coverage"):
        if regime == "anchored":
            wanted = retry(entry, ASK.format(index=index_text, note=note, limit=fetch_limit),
                           min(400, max_tokens), attempts)
            asked = parse_ids(wanted, fetch_limit)
        else:
            # Coverage inversion, proposed by the agent `zhaoxuan` on Moltbook:
            # model the gaps before looking at the shelf, then spend the fetches
            # on what the note does not already carry.
            covered = retry(entry, COVERAGE.format(note=note), min(700, max_tokens), attempts)
            wanted = retry(entry, INVERT.format(map=covered.strip(), index=index_text, limit=fetch_limit),
                           min(1200, max_tokens), attempts)
            marks = parse_marks(wanted)
            # The marking list names every identifier, so the request has to be
            # read from the FETCH line alone; reading the whole reply would fetch
            # whatever happened to be marked first.
            asked = order_by_gap(parse_ids(fetch_line(wanted), fetch_limit), marks)
        entries = bl.fetch(ledger, asked, fetch_limit)
        got = [item["id"] for item in entries]
        preamble = INDEX_NOTE.format(index=index_text)
        if entries:
            preamble += RETRIEVED.format(entries=render_entries(entries))
    content = retry(entry, note + "\n\n" + preamble + instruction, max_tokens, attempts)
    return {"text": content.strip(), "asked": asked, "retrieved": got, "marks": marks}


def retry(entry: dict, prompt: str, max_tokens: int, attempts: int) -> str:
    last: AdapterError | None = None
    for _ in range(attempts):
        try:
            content, _served = call(entry, prompt, max_tokens)
            return content
        except AdapterError as exc:
            last = exc
    raise last or AdapterError("no answer")


def write_chain(regime: str, entry: dict, source: str, instruction: str, hops: int,
                ledger: list[dict], index_text: str, fetch_limit: int, max_tokens: int,
                words: int | None) -> list[dict]:
    chain = []
    current = source
    for hop in range(1, hops + 1):
        # Hop 1 writes from the document itself: the archive would be a copy of
        # what the writer is already reading, so every regime starts identically
        # and any difference between them is created by the handoffs, not by the
        # first reading.
        step = (write_hop("bare", entry, current, instruction, ledger, index_text, fetch_limit, max_tokens)
                if hop == 1 else
                write_hop(regime, entry, current, instruction, ledger, index_text, fetch_limit, max_tokens))
        text, cut = hb.trim(step["text"], words)
        by_id = {item["id"]: item["text"] for item in ledger}
        chain.append({"hop": hop, "text": text, "words_written": len(step["text"].split()),
                      "words_kept": len(text.split()), "trimmed": cut, "sha256": sha256_text(text),
                      "asked": step["asked"], "retrieved": step["retrieved"], "marks": step["marks"],
                      # Whether each fetch went after something the note had already
                      # lost, judged against the note the writer was holding.
                      "on_a_gap": [entry_id for entry_id in step["retrieved"]
                                   if not already_carried(by_id.get(entry_id, ""), current)]})
        current = text
    return chain


def run_case(case: dict, document: str, quiz: dict, rendered: list[dict], key: dict[str, str],
             generator: dict, reader: dict, read_at: list[int], ledger: list[dict], index_text: str,
             fetch_limit: int, max_tokens: int, out: Path, words: int | None) -> dict:
    regime, repeat = case["strategy"], case["repeat"]
    stored = out / ("%s-%02d.json" % (regime, repeat))
    if stored.is_file():
        return json.loads(stored.read_text(encoding="utf-8"))
    record = {"strategy": regime, "repeat": repeat, "read_at": read_at, "word_limit": words,
              "fetch_limit": fetch_limit, "written_at_utc": now()}

    def failed(reason: str) -> dict:
        record["error"] = reason[:300]
        (out / ("%s-%02d.failed.json" % (regime, repeat))).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return record

    try:
        chain = write_chain(regime, generator, document, case["instruction"], max(read_at),
                            ledger, index_text, fetch_limit, max_tokens, words)
    except (AdapterError, ValueError) as exc:
        return failed(str(exc))
    record["chain"] = chain
    grades = {}
    for hop in read_at:
        prompt = hq.reader_prompt(quiz, rendered, chain[hop - 1]["text"])
        try:
            content, _served = call(reader, prompt, int(reader.get("max_tokens", 2000)))
        except AdapterError as exc:
            return failed("hop %d: %s" % (hop, exc))
        answers, problems = hq.parse_answers(content, [item["id"] for item in rendered])
        if not answers:
            return failed("hop %d: reader returned no usable answer" % hop)
        grades[str(hop)] = {"answers": answers, "problems": problems, **hq.grade(answers, key, rendered)}
    record["grades"] = grades
    stored.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def retrieval_log(records: list[dict], ledger: list[dict]) -> dict:
    """What each retrieving regime chose to look up, and whether it aimed at gaps.

    Gap-targeting precision is the share of fetches that went after something the
    note no longer carried. It is the metric that separates a protocol which
    searches better from one that merely searches.
    """
    labels = {entry["id"]: entry["label"] for entry in ledger}
    out: dict[str, dict] = {}
    for regime in ("anchored", "coverage"):
        counts: dict[str, int] = {}
        total = on_gap = 0
        for record in records:
            if record.get("strategy") != regime:
                continue
            for step in record.get("chain", []):
                for entry_id in step.get("retrieved", []):
                    counts[entry_id] = counts.get(entry_id, 0) + 1
                    total += 1
                on_gap += len(step.get("on_a_gap") or ())
        if not total:
            continue
        ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        out[regime] = {"retrievals": total, "distinct_entries": len(counts),
                       "on_a_gap": on_gap, "gap_targeting_pct": round(100.0 * on_gap / total, 1),
                       "most_retrieved": [{"id": entry_id, "times": times, "label": labels.get(entry_id, "?")}
                                          for entry_id, times in ranked[:10]]}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--read-at", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--words", type=int, default=150)
    parser.add_argument("--fetch", type=int, default=4, help="entries the anchored regime may retrieve per hop")
    parser.add_argument("--regimes", nargs="*", default=list(REGIMES))
    parser.add_argument("--instruction", default="checklist")
    parser.add_argument("--generator-model", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--reader-model", default="openai/gpt-oss-120b")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    location = private.get("keys", {}).get(args.key)
    if not location:
        raise SystemExit("no key location configured for %r" % args.key)
    common = {k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}
    generator = {"evaluator_id": "anchor-writer", "provider": args.key, "model": args.generator_model,
                 "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
                 "extra_body": {"reasoning": {"enabled": False}}, **common}
    reader = {"evaluator_id": "anchor-reader", "provider": args.key, "model": args.reader_model,
              "endpoint": args.endpoint, "json_mode": False, "max_tokens": 2000,
              "extra_body": {"reasoning": {"effort": "low"}}, **common}

    document = args.document.read_text(encoding="utf-8")
    ledger_file = json.loads(args.ledger.read_text(encoding="utf-8"))
    if ledger_file["document_sha256"] != sha256_text(document):
        raise SystemExit("the ledger was built from a different version of this document")
    ledger = ledger_file["entries"]
    index_text = bl.render_index(ledger)

    quiz = json.loads(args.quiz.read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, args.document.name + ":" + quiz["quiz_version"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "answer-key.json").write_text(
        json.dumps({"key": key, "rendered": rendered}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    instruction = hb.strategies(args.words)[args.instruction]
    cases = [{"strategy": regime, "repeat": index, "instruction": instruction}
             for regime in args.regimes for index in range(1, args.repeats + 1)]
    read_at = sorted(set(args.read_at))
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(
            lambda case: run_case(case, document, quiz, rendered, key, generator, reader, read_at,
                                  ledger, index_text, args.fetch, args.max_tokens, args.out, args.words),
            cases))
    failed = [record for record in records if "grades" not in record]
    tables = {str(hop): hb.summarise(records, hop, control=CONTROL) for hop in read_at}
    meta = {"document": args.document.name, "ledger_entries": len(ledger), "fetch_limit": args.fetch,
            "instruction": args.instruction,
            "fact_questions": sum(1 for item in rendered if item["kind"] == "fact"),
            "absent_questions": sum(1 for item in rendered if item["kind"] == "absent"),
            "read_at": read_at, "repeats": args.repeats, "generator": args.generator_model,
            "reader": args.reader_model, "word_limit": args.words, "failed_runs": len(failed),
            "failures": [{"strategy": row["strategy"], "repeat": row["repeat"], "error": row.get("error", "")[:160]}
                         for row in failed],
            "retrieval": retrieval_log(records, ledger)}
    (args.out / "report.json").write_text(
        json.dumps({"meta": meta, "by_hop": tables}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(hb.render_report(tables, meta, control=CONTROL), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "failed_runs": len(failed), "by_hop": tables,
                      "retrieval": meta["retrieval"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
