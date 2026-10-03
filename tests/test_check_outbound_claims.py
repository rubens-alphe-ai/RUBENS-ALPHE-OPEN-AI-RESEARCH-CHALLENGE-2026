"""The tripwire for claims this project has already made and had to withdraw."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_outbound_claims as oc  # noqa: E402


def rules(text: str) -> set[str]:
    return {rule for _, rule, _, _ in oc.check(text)}


class CaughtTests(unittest.TestCase):
    def test_the_exclusivity_claim_that_was_refuted_is_caught(self) -> None:
        self.assertIn("exclusivity", rules("Nous sommes les seuls à vérifier que le quiz mesure."))
        self.assertIn("exclusivity", rules("Personne ne vend la validité du quiz lui-même."))
        self.assertIn("exclusivity", rules("We are the only company doing this."))

    def test_medqa_items_called_mis_keyed_are_caught(self) -> None:
        self.assertIn("medqa-keys", rules("Sur MedQA, 138 questions ont une clé fausse."))

    def test_a_screening_count_presented_as_a_verdict_is_caught(self) -> None:
        self.assertIn("screening-as-verdict", rules("We found 324 wrong keys across the benchmarks."))

    def test_the_ai_act_presented_as_already_binding_is_caught(self) -> None:
        self.assertIn("ai-act-date", rules("L'AI Act impose désormais de déclarer les métriques."))

    def test_customers_and_guarantees_are_caught(self) -> None:
        self.assertIn("customers", rules("Trusted by leading banks."))
        self.assertIn("guarantee", rules("Savings guaranteed within a month."))


class EquivalenceTests(unittest.TestCase):
    def test_no_gap_read_as_equal_is_caught(self) -> None:
        self.assertIn("equivalence", rules("Les deux modèles se valent sur vos tâches."))
        self.assertIn("equivalence", rules("The cheaper model is as good as the leader."))

    def test_a_question_or_a_negation_passes(self) -> None:
        self.assertEqual(rules("Un modèle moins cher ferait-il aussi bien ? Un modèle moins cher est-il aussi bon ?"), set())
        self.assertEqual(rules("Not established does not mean they are equivalent."), set())


class AllowedTests(unittest.TestCase):
    def test_negated_certification_and_guarantee_pass(self) -> None:
        self.assertEqual(rules("Ce n'est pas une certification, et aucune économie n'est garantie."), set())
        self.assertEqual(rules("It is not a certification."), set())

    def test_the_ai_act_with_its_date_passes(self) -> None:
        self.assertEqual(rules("À partir du 2 décembre 2027, l'AI Act exige de déclarer ces métriques."), set())

    def test_medqa_stated_carefully_passes(self) -> None:
        self.assertEqual(rules("Sur MedQA, ces questions n'ont pas été vérifiées : ce ne sont pas des clés fausses."), set())

    def test_the_idiom_le_seul_fait_is_not_an_exclusivity_claim(self) -> None:
        # A false alarm found on a real draft: "by the mere fact of being written".
        self.assertEqual(rules("Ils ne sont pas autorisés par le seul fait d'être rédigés."), set())

    def test_a_negation_at_the_start_of_the_sentence_counts(self) -> None:
        self.assertEqual(rules("Pas de client inventé, de gain garanti ou de promesse de certification."), set())

    def test_the_corrected_positioning_passes(self) -> None:
        text = ("D'autres outillent la relecture des tests. Nous apportons une analyse question par question "
                "dont la fiabilité est mesurée contre des experts.")
        self.assertEqual(rules(text), set())


if __name__ == "__main__":
    unittest.main()


class FrenchNegationTests(unittest.TestCase):
    def test_ne_before_the_word_counts_as_a_negation(self) -> None:
        self.assertEqual(rules("Ce que nous ne garantissons pas : un résultat particulier."), set())
        self.assertIn("guarantee", rules("Résultat garanti en 48 heures."))
