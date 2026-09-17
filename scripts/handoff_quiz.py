#!/usr/bin/env python3
"""Score handoff fidelity by questions with known answers, not by a judge model.

MEM-001 to MEM-003 scored free-text handoffs with language-model judges. The
judges were the weakest part of every experiment: free shared capacity failed
for hours, totals were miscomputed, one judge gave 100 to half the answers, two
judges differed by 20 points on the same answer, and a capable generator's
wording let a judge guess the condition.

This design removes the judge. Stage 1 is unchanged: a generator reads a
project state and writes a handoff. Stage 2: a reader model that sees only that
handoff text answers a fixed multiple-choice quiz whose key was written from the
state before any trial. The script grades by comparing letters.

* fact questions measure what the handoff transferred correctly;
* absent questions ask for things the state never contained; any answer other
  than "the text does not say" is an invention, so fabrication becomes a rate.

Option order is shuffled per question with a fixed seed, so the key is not a
pattern. Grading and analysis are deterministic: anyone can rerun them from the
stored reader answers and obtain the same verdict.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path

LETTERS = "ABCDE"

READER_HEADER = """Below is a text written by another system to describe a project.

Answer every question using ONLY this text. Do not use outside knowledge and do
not guess. If the text does not give the answer, choose the option "{not_stated}".

Return ONE JSON object and nothing else, of the form
{{"answers": {{"Q01": "A", "Q02": "C", ...}}}}
with exactly one letter for each of these ids: {ids}.

=== TEXT ===
{text}
=== END OF TEXT ===

=== QUESTIONS ===
"""


def seed_from(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def render_quiz(quiz: dict, seed_material: str) -> tuple[list[dict], dict[str, str]]:
    """Return rendered questions and the letter key. Deterministic for a seed."""
    rng = random.Random(seed_from(seed_material))
    not_stated = quiz["not_stated_option"]
    rendered, key = [], {}
    for question in quiz["questions"]:
        answer = question["correct"] if question["kind"] == "fact" else not_stated
        head = ([question["correct"]] if question["kind"] == "fact" else []) + list(question["distractors"])
        rng.shuffle(head)
        options = head + [not_stated]  # "does not say" is always the last letter
        if len(options) != len(LETTERS):
            raise ValueError("%s must have exactly %d options" % (question["id"], len(LETTERS)))
        key[question["id"]] = LETTERS[options.index(answer)]
        rendered.append({"id": question["id"], "kind": question["kind"], "question": question["question"],
                         "options": dict(zip(LETTERS, options))})
    return rendered, key


def reader_prompt(quiz: dict, rendered: list[dict], handoff_text: str) -> str:
    ids = ", ".join(item["id"] for item in rendered)
    parts = [READER_HEADER.format(not_stated=quiz["not_stated_option"], ids=ids, text=handoff_text.strip())]
    for item in rendered:
        parts.append("\n%s. %s\n" % (item["id"], item["question"]))
        parts.extend("  %s) %s\n" % (letter, text) for letter, text in item["options"].items())
    return "".join(parts)


def parse_answers(raw: str, ids: list[str]) -> tuple[dict[str, str], list[str]]:
    """Extract one letter per id; report what is missing or invalid."""
    decoder = json.JSONDecoder()
    payload = None
    index = raw.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            index = raw.find("{", index + 1)
            continue
        if isinstance(value, dict) and isinstance(value.get("answers"), dict):
            payload = value["answers"]
            break
        index = raw.find("{", index + 1)
    if payload is None:
        return {}, ["no JSON object with an answers field"]
    answers, problems = {}, []
    for question_id in ids:
        value = str(payload.get(question_id, "")).strip().upper()
        match = re.fullmatch(r"\(?([A-E])\)?\.?", value)
        if match:
            answers[question_id] = match.group(1)
        else:
            problems.append("%s: %r" % (question_id, payload.get(question_id)))
    return answers, problems


def grade(answers: dict[str, str], key: dict[str, str], rendered: list[dict]) -> dict:
    """Missing or invalid answers count as wrong, never as 'does not say'."""
    not_stated = LETTERS[-1]
    facts = [item["id"] for item in rendered if item["kind"] == "fact"]
    absent = [item["id"] for item in rendered if item["kind"] == "absent"]
    fact_correct = sum(1 for q in facts if answers.get(q) == key[q])
    fact_not_stated = sum(1 for q in facts if answers.get(q) == not_stated)
    inventions = sum(1 for q in absent if answers.get(q) not in (None, not_stated))
    return {"fact_questions": len(facts), "fact_correct": fact_correct,
            "fact_accuracy": fact_correct / len(facts) if facts else 0.0,
            "fact_answered_not_stated": fact_not_stated,
            "fact_wrong_claims": len(facts) - fact_correct - fact_not_stated - sum(1 for q in facts if q not in answers),
            "absent_questions": len(absent), "inventions": inventions,
            "unanswered": sum(1 for q in facts + absent if q not in answers)}


T_975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
         20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
         29: 2.045, 30: 2.042}


def decide(pairs: list[dict], rule: dict) -> dict:
    """Paired analysis of fact accuracy and inventions, with a pre-registered rule.

    pairs: [{"pair_id", "baseline": grade(...), "structured": grade(...)}]
    rule: {"keep_min_delta_pp", "invention_margin"}
    """
    deltas = [100.0 * (p["structured"]["fact_accuracy"] - p["baseline"]["fact_accuracy"]) for p in pairs]
    n = len(deltas)
    summary = {"pairs": n}
    if n < 2:
        return {"decision": "INCONCLUSIVE", "reason_codes": ["TOO_FEW_PAIRS"], "summary": summary}
    mean = sum(deltas) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in deltas) / (n - 1))
    half = T_975.get(n - 1, 1.96) * sd / math.sqrt(n)
    inventions = {c: sum(p[c]["inventions"] for p in pairs) for c in ("baseline", "structured")}
    accuracy = {c: 100.0 * sum(p[c]["fact_accuracy"] for p in pairs) / n for c in ("baseline", "structured")}
    summary.update({"mean_fact_accuracy_pp": accuracy, "mean_paired_delta_pp": mean, "sd_delta_pp": sd,
                    "ci95_delta_pp": [mean - half, mean + half], "inventions": inventions,
                    "pairs_structured_better": sum(1 for d in deltas if d > 0),
                    "pairs_structured_worse": sum(1 for d in deltas if d < 0), "pairs_equal": sum(1 for d in deltas if d == 0)})
    threshold = float(rule["keep_min_delta_pp"])
    margin = int(rule["invention_margin"])
    if inventions["structured"] > inventions["baseline"] + margin:
        return {"decision": "REJECT", "reason_codes": ["STRUCTURED_INVENTS_MORE"], "summary": summary}
    if mean >= threshold and mean - half > 0:
        return {"decision": "PROVISIONAL_KEEP", "reason_codes": [], "summary": summary}
    if mean + half < threshold:
        return {"decision": "REJECT", "reason_codes": ["IMPROVEMENT_BELOW_THRESHOLD_EXCLUDED"], "summary": summary}
    return {"decision": "INCONCLUSIVE", "reason_codes": ["CONFIDENCE_INTERVAL_SPANS_THRESHOLD"], "summary": summary}
