#!/usr/bin/env python3
"""Turn a document into a verifiable ledger: numbered entries, each hashed.

Stage 2 of the Continuity Programme asks whether a chain that can *check*
something loses differently from one that can only remember. That requires an
archive, and an archive built by a model would be a second source of error —
and worse, a channel through which the quiz could leak. So this builds one
without calling anything: the document is split on sentence boundaries, each
entry keeps its text verbatim, and each carries the SHA-256 of that text.

Two things are separable in what an archive gives a writer, and the experiment
separates them:

- the **index**: knowing that entry 14 exists and roughly what it is about,
  which tells a chain what it has already dropped;
- **retrieval**: getting entry 14 back, verbatim and verified.

A label is the entry's first few words with every digit masked. An index is a
table of contents: it names a topic so you can find it, it does not quote the
value. Masking the digits keeps that property against the kind of fact these
quizzes ask about — counts, dates, amounts — so that consulting the index cannot
substitute for retrieving the entry. Whatever leak remains is not assumed away:
the experiment runs an index-only arm whose whole purpose is to measure it.

  python scripts/build_ledger.py --document experiments/.../clinic.md --out .../ledger-clinic.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
DIGIT = re.compile(r"\d")
LABEL_WORDS = 6


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entries(document: str, label_words: int = LABEL_WORDS) -> list[dict]:
    """One entry per sentence, in reading order, headings kept as their own entry.

    Paragraphs are unwrapped before splitting: these documents are hard-wrapped
    at a fixed column, and cutting on line breaks would produce entries ending
    mid-sentence, which is an artefact of the file rather than of the text.
    """
    found = []
    for block in document.split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("#"):
                found.append(line)
        body = " ".join(line for line in lines if not line.startswith("#"))
        for piece in SENTENCE_END.split(body):
            piece = piece.strip()
            if piece:
                found.append(piece)
    ledger = []
    for index, text in enumerate(found, start=1):
        words = DIGIT.sub("#", text.lstrip("#").strip()).split()
        ledger.append({"id": "E%02d" % index, "text": text, "sha256": sha256_text(text),
                       "label": " ".join(words[:label_words]) + ("…" if len(words) > label_words else "")})
    return ledger


def render_index(ledger: list[dict]) -> str:
    """What a writer sees when it may consult the archive but not read it."""
    return "\n".join("%s  %s" % (entry["id"], entry["label"]) for entry in ledger)


def fetch(ledger: list[dict], ids: list[str], limit: int) -> list[dict]:
    """The first `limit` valid ids asked for, each checked against its hash.

    A retrieval that did not match its recorded hash would mean the archive
    changed under the experiment; it raises rather than returning a fact whose
    provenance is no longer established.
    """
    by_id = {entry["id"]: entry for entry in ledger}
    out = []
    for wanted in ids:
        entry = by_id.get(wanted.strip().upper())
        if entry is None or entry in out:
            continue
        if sha256_text(entry["text"]) != entry["sha256"]:
            raise ValueError("ledger entry %s does not match its hash" % entry["id"])
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label-words", type=int, default=LABEL_WORDS)
    args = parser.parse_args()

    document = args.document.read_text(encoding="utf-8")
    ledger = entries(document, args.label_words)
    record = {"record_version": "RA-PSI-LEDGER-V1", "document": args.document.name,
              "document_sha256": sha256_text(document), "label_words": args.label_words,
              "entries": ledger}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"document": args.document.name, "entries": len(ledger),
                      "median_words": sorted(len(e["text"].split()) for e in ledger)[len(ledger) // 2]}, indent=2))


if __name__ == "__main__":
    main()
