"""The sealed reader panel: neither side can move after the fact."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_quiz as hq  # noqa: E402
import panel  # noqa: E402

QUIZ = {
    "quiz_version": "PANEL-TEST-V1",
    "not_stated_option": "The text does not say.",
    "questions": [
        {"id": "Q01", "kind": "fact", "question": "How many nodes?",
         "correct": "six", "distractors": ["two", "four", "eight"]},
        {"id": "Q02", "kind": "absent", "question": "Who signs the invoices?",
         "distractors": ["the treasurer", "the chair", "nobody", "the auditor"]},
    ],
}


def sealed(tmp: Path, nonce: str | None = None) -> argparse.Namespace:
    quiz_path = tmp / "QUIZ.json"
    quiz_path.write_text(json.dumps(QUIZ), encoding="utf-8")
    handoff = tmp / "handoff.txt"
    handoff.write_text("The cluster runs six nodes.", encoding="utf-8")
    return argparse.Namespace(quiz=quiz_path, handoff=handoff, out=tmp / "public",
                              panel=tmp / "public", answers=tmp / "answers",
                              private=tmp / "private", nonce=nonce)


class SealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.args = sealed(self.tmp)
        self.commitment = panel.seal(self.args)

    def test_the_published_folder_never_contains_the_key_or_the_nonce(self) -> None:
        for path in (self.args.out / "PANEL.md", self.args.out / "rendered.json",
                     self.args.out / "commitment.json"):
            text = path.read_text(encoding="utf-8")
            secret = json.loads((self.args.private / "panel-secret.json").read_text(encoding="utf-8"))
            self.assertNotIn(secret["nonce"], text, path.name)
            self.assertNotIn(json.dumps(secret["key"]), text, path.name)

    def test_the_commitment_hashes_the_key_before_any_answer_exists(self) -> None:
        self.assertEqual(len(self.commitment["key_sha256"]), 64)
        self.assertEqual(self.commitment["questions"], 2)

    def test_a_reveal_reproduces_the_rendering_from_the_nonce_alone(self) -> None:
        secret = json.loads((self.args.private / "panel-secret.json").read_text(encoding="utf-8"))
        again, key = hq.render_quiz(QUIZ, secret["nonce"])
        published = json.loads((self.args.out / "rendered.json").read_text(encoding="utf-8"))
        self.assertEqual(again, published)
        self.assertEqual(key, secret["key"])

    def test_the_key_depends_on_the_nonce(self) -> None:
        # Without this the sealing is decorative: anyone holding the quiz could
        # recompute the key from the published rendering. Two questions collide
        # by chance often enough that one pair proves nothing, so this looks at
        # a spread of nonces.
        keys = {json.dumps(hq.render_quiz(QUIZ, "nonce-%d" % index)[1], sort_keys=True) for index in range(12)}
        self.assertGreater(len(keys), 1)

    def test_letters_are_read_from_however_a_responder_wrote_them(self) -> None:
        written = "Q01: (B)\nQ02 - e\nQ03 A"
        answers, problems = panel.read_letters(written, ["Q01", "Q02", "Q03"])
        self.assertEqual(answers, {"Q01": "B", "Q02": "E", "Q03": "A"})
        self.assertEqual(problems, [])

    def test_a_missing_question_is_reported_rather_than_silently_dropped(self) -> None:
        answers, problems = panel.read_letters("Q01 A", ["Q01", "Q02"])
        self.assertEqual(answers, {"Q01": "A"})
        self.assertIn("Q02", problems[0])

    def test_reveal_refuses_when_the_secret_does_not_match_the_commitment(self) -> None:
        secret_path = self.args.private / "panel-secret.json"
        secret = json.loads(secret_path.read_text(encoding="utf-8"))
        secret["nonce"] = "tampered"
        secret_path.write_text(json.dumps(secret), encoding="utf-8")
        with self.assertRaises(SystemExit):
            panel.reveal(self.args)

    def test_reveal_writes_the_nonce_and_key_once_they_check_out(self) -> None:
        payload = panel.reveal(self.args)
        self.assertTrue(all(payload["checks"].values()))
        self.assertTrue((self.args.panel / "reveal.json").is_file())


class GradeTests(unittest.TestCase):
    def test_answers_are_graded_against_the_sealed_key_and_spread_reported(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        args = sealed(tmp)
        panel.seal(args)
        secret = json.loads((args.private / "panel-secret.json").read_text(encoding="utf-8"))
        args.answers.mkdir(parents=True, exist_ok=True)
        right = "\n".join("%s %s" % (qid, letter) for qid, letter in secret["key"].items())
        (args.answers / "good.json").write_text(
            json.dumps({"responder": "good", "model_family": "x", "answers_text": right}), encoding="utf-8")
        wrong_letter = "A" if secret["key"]["Q02"] != "A" else "B"
        (args.answers / "invents.json").write_text(
            json.dumps({"responder": "invents", "answers_text": "Q01 %s\nQ02 %s"
                        % (secret["key"]["Q01"], wrong_letter)}), encoding="utf-8")
        report = panel.grade(args)
        self.assertEqual(report["summary"]["responders"], 2)
        by_name = {row["responder"]: row for row in report["responders"]}
        self.assertEqual(by_name["good"]["inventions"], 0)
        self.assertEqual(by_name["invents"]["inventions"], 1)


if __name__ == "__main__":
    unittest.main()
