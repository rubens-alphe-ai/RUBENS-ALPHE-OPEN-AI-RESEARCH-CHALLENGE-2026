"""The QCM report finds a planted wrong key and re-marks the class with it fixed."""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_outbound_claims as oc  # noqa: E402
import qcm_report as qr  # noqa: E402


def class_csv(seed: int = 3, n: int = 40) -> str:
    rng = random.Random(seed)
    true = list("ABCDABCDAB")
    key = list(true)
    key[4] = "B"  # planted wrong key on Q5
    lines = ["Nom;" + ";".join("Q%d" % (j + 1) for j in range(10)), "CORRIGÉ;" + ";".join(key)]
    for s in range(n):
        th = rng.gauss(0, 1.2)
        row = []
        for j in range(10):
            p = 0.15 + 0.85 / (1 + math.exp(-2.4 * (th - (j - 5) / 4)))
            row.append(true[j] if rng.random() < p else ("B" if j == 4 else rng.choice([x for x in "ABCD" if x != true[j]])))
        lines.append("E%02d;" % s + ";".join(row))
    return "\n".join(lines)


class QcmTests(unittest.TestCase):
    def test_the_planted_wrong_key_is_found_with_the_right_letter(self) -> None:
        d = qr.parse(class_csv())
        a = qr.analyse(d)
        suspects = {it["q"]: it["suggestion"] for it in a["items"] if it["level"] == 3}
        self.assertEqual(suspects, {"Q5": "A"})
        self.assertEqual(a["rekey"], {4: "A"})

    def test_rekeying_raises_the_grades_of_students_who_answered_right(self) -> None:
        d = qr.parse(class_csv())
        a = qr.analyse(d)
        gained = [s for i, s in enumerate(a["students"]) if d["answers"][i][4] == "A"]
        self.assertTrue(all(s["rekeyed"] > s["marked"] for s in gained))

    def test_the_report_passes_the_claims_tripwire(self) -> None:
        d = qr.parse(class_csv())
        self.assertEqual(oc.check(qr.single_report("classe", d, qr.analyse(d))), [])


if __name__ == "__main__":
    unittest.main()
