#!/usr/bin/env python3
"""Refuse an outbound text that makes a claim this project has learned not to make.

Every rule here exists because the claim was made — by this project, in a
draft, a message or a strategy note — and turned out to be false or unsupported:

- **exclusivity** — "we are the only ones", "nobody else sells this". Written
  in a positioning note and refuted with sources: evaluation platforms tool
  human review, consultancies sell bespoke evaluations, a label-error detector
  remains a competitor.
- **MedQA keys** — calling MedQA items mis-keyed. At twenty respondents the
  screening list includes about one healthy item in seven, only seven items
  survive the strict list, and the audit declined to adjudicate them.
- **screening counts as verdicts** — "138 wrong keys", "324 wrong keys".
- **AI Act already in force for high-risk systems** — their obligations apply
  from 2 December 2027, or 2 August 2028 for AI in regulated products.
- **certification, guarantees, customers** — there are none.

It is a tripwire, not a judge: a flagged line is a line a person must read
before the text goes out. A clean run is not proof that a text is true — only
that it avoids the mistakes already made once.

  python scripts/check_outbound_claims.py draft.md [more.md ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

NEGATION = re.compile(r"\b(pas|ni|jamais|aucune?|not|no|never|nor|without|sans)\b", re.I)

RULES = [
    ("exclusivity",
     re.compile(r"\b((nous sommes|on est|we are|we're) (les seuls|le seul|la seule|the only)|"
                r"(les seuls|le seul|la seule|seuls) (à|sur le marché)|personne d'autre|"
                r"personne ne (vend|fait|propose|vérifie)|nobody else|no one else|"
                r"the only (one|ones|company|tool|team|service)|monopol\w*|unique au monde|"
                r"le créneau est libre)\b", re.I),
     "Exclusivity was claimed once and refuted with sources. Say what we bring that is specific, "
     "not that nobody else does it."),
    ("certification",
     re.compile(r"\bcertifi\w*", re.I),
     "There is no certification. Allowed only in a negation such as 'not a certification'."),
    ("guarantee",
     re.compile(r"\b(garanti\w*|guarantee\w*)", re.I),
     "No saving or result is guaranteed. Allowed only in a negation."),
    ("customers",
     re.compile(r"\b(nos clients|nos références|our (clients|customers)|customers include|trusted by|"
                r"utilisé par|used by)\b", re.I),
     "There are no customers yet."),
    ("screening-as-verdict",
     re.compile(r"\b(138|324)\b[^.\n]{0,40}\b(clés?|keys?|erreurs?|errors?|mis-?keyed|fausses?|wrong)", re.I),
     "Screening counts are not verdicts: say 'on the strict list' and give the strict count."),
]

MEDQA = re.compile(r"\bmed\s?qa\b", re.I)
KEY_ERROR = re.compile(r"(clés? (de correction )?fausses?|erreurs? de correction|mis-?keyed|wrong (answer )?keys?|"
                       r"key errors?|corrigés? faux)", re.I)
AI_ACT = re.compile(r"\bAI Act\b", re.I)
IN_FORCE = re.compile(r"\b(impose|imposent|oblige|obligent|requires|require|exige|doit désormais|must now|"
                      r"en vigueur|in force|applies now|s'applique déjà)\b", re.I)
DATES = re.compile(r"\b(2027|2028)\b")


def sentences(text: str):
    for number, line in enumerate(text.splitlines(), 1):
        for piece in re.split(r"(?<=[.!?])\s+", line):
            if piece.strip():
                yield number, piece


def check(text: str) -> list[tuple[int, str, str, str]]:
    found = []
    for number, sentence in sentences(text):
        for name, pattern, why in RULES:
            for match in pattern.finditer(sentence):
                before = sentence[:match.start()]
                if name in ("certification", "guarantee") and NEGATION.search(before):
                    continue
                found.append((number, name, sentence.strip(), why))
                break
        if MEDQA.search(sentence) and KEY_ERROR.search(sentence) and not NEGATION.search(sentence):
            found.append((number, "medqa-keys", sentence.strip(),
                          "MedQA items have not been adjudicated; never call them mis-keyed."))
        if AI_ACT.search(sentence) and IN_FORCE.search(sentence) and not DATES.search(sentence):
            found.append((number, "ai-act-date", sentence.strip(),
                          "High-risk obligations apply from 2 December 2027 (2 August 2028 for regulated "
                          "products). State the date or do not claim an obligation."))
    return found


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("give one or more text files to check")
    total = 0
    for name in sys.argv[1:]:
        path = Path(name)
        for number, rule, sentence, why in check(path.read_text(encoding="utf-8")):
            total += 1
            print("%s:%d [%s] %s\n    -> %s" % (path, number, rule, sentence[:200], why))
    if total:
        print("\n%d line(s) to read before this goes out." % total)
        raise SystemExit(1)
    print("no known false claim found (this is not proof the text is true)")


if __name__ == "__main__":
    main()
