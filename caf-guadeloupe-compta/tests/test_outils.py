import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compta_auto.cloture import controler_balance  # noqa: E402
from compta_auto.fournisseurs import controler_factures, iban_valide  # noqa: E402
from compta_auto.indus import analyser_indus  # noqa: E402
from compta_auto.lecture import ColonnesManquantes, convertir_montant, lire_table  # noqa: E402
from compta_auto.rapprochement import rapprocher  # noqa: E402

REF = pd.Timestamp("2026-10-31")
IBAN_OK = "FR7630006000011234567890189"


class TestLecture(unittest.TestCase):
    def test_montants_francais(self):
        self.assertEqual(convertir_montant("1 234,56"), 1234.56)
        self.assertEqual(convertir_montant("1.234,56"), 1234.56)
        self.assertEqual(convertir_montant("-12,5 €"), -12.5)
        self.assertEqual(convertir_montant("1234.56"), 1234.56)
        self.assertEqual(convertir_montant(""), 0.0)

    def test_csv_point_virgule_cp1252(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "x.csv"
            chemin.write_bytes("Date;Libellé;Montant\n01/10/2026;Frais bancaires;-12,50\n".encode("cp1252"))
            df = lire_table(chemin)
        self.assertEqual(list(df.columns), ["date", "libelle", "montant"])
        self.assertEqual(df.iloc[0]["libelle"], "Frais bancaires")

    def test_colonne_manquante(self):
        with self.assertRaises(ColonnesManquantes):
            rapprocher(pd.DataFrame({"date": []}), pd.DataFrame({"date": []}))


class TestRapprochement(unittest.TestCase):
    def setUp(self):
        self.releve = pd.DataFrame([
            {"date": "02/10/2026", "libelle": "VIR A", "reference": "R1", "montant": "100,00"},
            {"date": "05/10/2026", "libelle": "PRLV B", "reference": "", "montant": "-50,00"},
            {"date": "10/10/2026", "libelle": "REMISE", "reference": "", "montant": "300,00"},
            {"date": "20/10/2026", "libelle": "FRAIS", "reference": "", "montant": "-8,00"},
        ])
        self.gl = pd.DataFrame([
            {"date": "01/10/2026", "piece": "1", "libelle": "a", "reference": "R1", "debit": "100", "credit": ""},
            {"date": "03/10/2026", "piece": "2", "libelle": "b", "reference": "", "debit": "", "credit": "50"},
            {"date": "09/10/2026", "piece": "3", "libelle": "c1", "reference": "", "debit": "120", "credit": ""},
            {"date": "09/10/2026", "piece": "4", "libelle": "c2", "reference": "", "debit": "180", "credit": ""},
            {"date": "25/10/2026", "piece": "5", "libelle": "chq", "reference": "", "debit": "", "credit": "70"},
        ])

    def test_trois_passes_et_suspens(self):
        res = rapprocher(self.releve, self.gl, tolerance_jours=3)
        confiances = res.lettrages.groupby("code_lettrage")["confiance"].first().tolist()
        self.assertEqual(confiances, ["HAUTE", "MOYENNE", "A_VERIFIER"])
        self.assertEqual(res.releve_non_lettre["libelle"].tolist(), ["FRAIS"])
        self.assertEqual(res.compta_non_lettree["piece"].tolist(), ["5"])
        synthese = dict(zip(res.synthese["indicateur"], res.synthese["valeur"]))
        self.assertEqual(synthese["Écart (€)"], synthese["Écart expliqué par les non-lettrés (€)"])

    def test_hors_tolerance(self):
        res = rapprocher(self.releve, self.gl, tolerance_jours=0)
        self.assertIn("PRLV B", res.releve_non_lettre["libelle"].tolist())


class TestFournisseurs(unittest.TestCase):
    def test_iban(self):
        self.assertTrue(iban_valide(IBAN_OK))
        self.assertTrue(iban_valide("FR76 3000 6000 0112 3456 7890 189"))
        self.assertFalse(iban_valide("FR7630006000011234567890188"))

    def test_regles(self):
        base = {"fournisseur_id": "F1", "fournisseur": "Alpha", "date_facture": "01/10/2026",
                "date_echeance": "30/11/2026", "iban": IBAN_OK}
        factures = pd.DataFrame([
            {**base, "numero_facture": "FA-001", "montant_ttc": "1000", "numero_commande": "C1"},
            {**base, "numero_facture": "FA001", "montant_ttc": "1000", "numero_commande": "C1"},
            {**base, "numero_facture": "FA-002", "montant_ttc": "500", "numero_commande": "C9",
             "iban": "FR7610278000000001234567890"},
        ])
        commandes = pd.DataFrame([{"numero_commande": "C1", "montant_ttc": "1000"}])
        referentiel = pd.DataFrame([{"fournisseur_id": "F1", "iban": IBAN_OK, "date_modif_iban": "01/01/2025"}])
        statut, anomalies = controler_factures(factures, REF, commandes, referentiel)
        regles = set(anomalies["regle"])
        self.assertIn("F1 doublon exact", regles)
        self.assertIn("F3 commande", regles)
        self.assertIn("F4 IBAN", regles)
        self.assertTrue((statut["statut"] == "BLOQUÉE").all())

    def test_facture_saine(self):
        factures = pd.DataFrame([{"fournisseur_id": "F1", "fournisseur": "Alpha", "numero_facture": "1",
                                  "date_facture": "01/10/2026", "date_echeance": "30/11/2026",
                                  "montant_ttc": "10", "iban": IBAN_OK}])
        statut, anomalies = controler_factures(factures, REF)
        self.assertTrue(anomalies.empty)
        self.assertEqual(statut.iloc[0]["statut"], "PRÊTE")


class TestIndus(unittest.TestCase):
    def test_balance_et_relances(self):
        creances = pd.DataFrame([
            {"numero_dossier": "D1", "date_constat": "15/10/2026", "montant_initial": "100", "montant_recouvre": "0"},
            {"numero_dossier": "D2", "date_constat": "01/01/2025", "montant_initial": "900", "montant_recouvre": "0"},
            {"numero_dossier": "D3", "date_constat": "01/04/2026", "montant_initial": "600", "montant_recouvre": "200"},
            {"numero_dossier": "D4", "date_constat": "01/04/2026", "montant_initial": "50", "montant_recouvre": "50"},
        ])
        echeancier = pd.DataFrame([
            {"numero_dossier": "D3", "date_echeance": "01/08/2026", "montant_prevu": "100", "montant_paye": "0"},
            {"numero_dossier": "D3", "date_echeance": "01/09/2026", "montant_prevu": "100", "montant_paye": "0"},
            {"numero_dossier": "D3", "date_echeance": "01/12/2026", "montant_prevu": "100", "montant_paye": "0"},
        ])
        res = analyser_indus(creances, REF, echeancier)
        total = res["balance_agee"].iloc[-1]
        self.assertEqual(total["nombre"], 3)
        self.assertEqual(total["solde"], 1400.0)
        relances = res["relances"].set_index("numero_dossier")
        self.assertEqual(relances.loc["D2", "priorite"], 1)
        self.assertEqual(relances.loc["D3", "echeances_impayees"], 2)
        self.assertNotIn("D1", relances.index)


class TestCloture(unittest.TestCase):
    def test_constats(self):
        balance = pd.DataFrame([
            {"compte": "512100", "libelle": "Banque", "solde_debiteur": "0", "solde_crediteur": "500"},
            {"compte": "471000", "libelle": "Attente", "solde_debiteur": "200", "solde_crediteur": "0"},
            {"compte": "606000", "libelle": "Achats", "solde_debiteur": "50000", "solde_crediteur": "0"},
            {"compte": "706000", "libelle": "Produits", "solde_debiteur": "0", "solde_crediteur": "49000"},
        ])
        n1 = balance.copy()
        n1.loc[2, "solde_debiteur"] = "20000"
        res = controler_balance(balance, n1)
        controles = res["constats"]["controle"].tolist()
        self.assertIn("C1 équilibre", controles)
        self.assertIn("C2 sens anormal", controles)
        self.assertIn("C3 compte d'attente", controles)
        self.assertIn("C4 variation", controles)


if __name__ == "__main__":
    unittest.main()
