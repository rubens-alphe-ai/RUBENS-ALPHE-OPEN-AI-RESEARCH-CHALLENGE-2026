"""Génère des exports FICTIFS pour essayer les outils sans données réelles.

    python exemples/generer_donnees.py            # écrit dans exemples/donnees/

Les fichiers imitent des exports « à la française » (séparateur ;,
montants 1234,56, dates jj/mm/aaaa) et contiennent volontairement des
anomalies que les contrôles doivent trouver.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

DOSSIER = Path(__file__).parent / "donnees"
DATE_REF = date(2026, 10, 31)


def iban_fr(bban: str) -> str:
    chiffres = "".join(str(int(c, 36)) for c in bban + "FR00")
    return f"FR{98 - int(chiffres) % 97:02d}{bban}"


def ecrire(df: pd.DataFrame, nom: str) -> None:
    df = df.copy()
    for col in df.columns:
        if df[col].dtype.kind == "f":
            df[col] = df[col].map(lambda v: f"{v:.2f}".replace(".", ","))
        elif isinstance(df[col].iloc[0], date):
            df[col] = df[col].map(lambda d: d.strftime("%d/%m/%Y") if isinstance(d, date) else d)
    df.to_csv(DOSSIER / nom, sep=";", index=False, encoding="cp1252")


def rapprochement(rnd: random.Random) -> None:
    releve, gl = [], []
    debut = date(2026, 10, 1)
    for k in range(120):
        jour = debut + timedelta(days=rnd.randint(0, 29))
        montant = round(rnd.uniform(50, 25_000), 2) * rnd.choice([1, -1])
        ref = f"VIR{k:05d}" if rnd.random() < 0.6 else ""
        decalage = rnd.randint(0, 2)
        releve.append({"date": jour + timedelta(days=decalage), "libelle": f"OPERATION {k}",
                       "reference": ref, "montant": montant})
        gl.append({"date": jour, "piece": f"P{k:05d}", "libelle": f"Ecriture {k}", "reference": ref,
                   "debit": montant if montant > 0 else 0.0, "credit": -montant if montant < 0 else 0.0})
    # remise groupée : 3 écritures, une seule ligne de relevé
    parts = [1200.0, 845.5, 310.25]
    for n, m in enumerate(parts):
        gl.append({"date": date(2026, 10, 15), "piece": f"RG{n}", "libelle": "Remise chèques",
                   "reference": "", "debit": m, "credit": 0.0})
    releve.append({"date": date(2026, 10, 16), "libelle": "REMISE CHEQUES", "reference": "",
                   "montant": sum(parts)})
    # anomalies : frais bancaires non comptabilisés, chèque émis non encaissé
    releve.append({"date": date(2026, 10, 30), "libelle": "FRAIS TENUE COMPTE", "reference": "",
                   "montant": -38.4})
    gl.append({"date": date(2026, 10, 29), "piece": "CHQ9921", "libelle": "Cheque fournisseur",
               "reference": "", "debit": 0.0, "credit": 1520.0})
    ecrire(pd.DataFrame(releve), "releve_bancaire.csv")
    ecrire(pd.DataFrame(gl), "grand_livre_512.csv")


def fournisseurs(rnd: random.Random) -> None:
    ref, cdes, fact = [], [], []
    for k in range(15):
        fid = f"F{k:03d}"
        iban = iban_fr(f"30004{k:05d}{rnd.randint(10**10, 10**11 - 1)}{rnd.randint(10, 99)}")
        modif = date(2025, 1, 10) if k != 4 else date(2026, 10, 20)
        ref.append({"fournisseur_id": fid, "fournisseur": f"Fournisseur {k}", "iban": iban,
                    "date_modif_iban": modif})
        for n in range(2):
            num_cde = f"BC{k:03d}{n}"
            montant = round(rnd.uniform(300, 15_000), 2)
            cdes.append({"numero_commande": num_cde, "montant_ttc": montant})
            d = DATE_REF - timedelta(days=rnd.randint(5, 40))
            fact.append({"fournisseur_id": fid, "fournisseur": f"Fournisseur {k}",
                         "numero_facture": f"FA-2026-{k:03d}{n}", "date_facture": d,
                         "date_echeance": d + timedelta(days=30), "montant_ttc": montant,
                         "iban": iban, "numero_commande": num_cde})
    fact.append({**fact[2], "numero_facture": fact[2]["numero_facture"].replace("-", "")})  # doublon exact
    fact[7] = {**fact[7], "iban": iban_fr("1027800000000123456789")}                      # IBAN changé
    fact[10] = {**fact[10], "montant_ttc": round(fact[10]["montant_ttc"] * 1.2, 2)}       # dépasse la commande
    fact[12] = {**fact[12], "iban": "FR7630004000000000000000000"}                         # IBAN invalide
    ecrire(pd.DataFrame(ref), "referentiel_fournisseurs.csv")
    ecrire(pd.DataFrame(cdes), "commandes.csv")
    ecrire(pd.DataFrame(fact), "factures.csv")


def indus(rnd: random.Random) -> None:
    creances, echeances = [], []
    for k in range(200):
        dossier = f"D{k:06d}"
        constat = DATE_REF - timedelta(days=rnd.randint(10, 1000))
        initial = round(rnd.uniform(80, 6000), 2)
        recouvre = round(initial * rnd.choice([0, 0, 0.25, 0.5, 1]), 2)
        creances.append({"numero_dossier": dossier, "date_constat": constat,
                         "montant_initial": initial, "montant_recouvre": recouvre})
        if 0 < recouvre < initial and rnd.random() < 0.7:
            for m in range(1, 7):
                ech = constat + timedelta(days=30 * m)
                prevu = round((initial - recouvre) / 6, 2)
                paye = prevu if rnd.random() < 0.8 else 0.0
                echeances.append({"numero_dossier": dossier, "date_echeance": ech,
                                  "montant_prevu": prevu, "montant_paye": paye})
    ecrire(pd.DataFrame(creances), "creances_indus.csv")
    ecrire(pd.DataFrame(echeances), "echeancier_indus.csv")


def cloture(rnd: random.Random) -> None:
    comptes = [("401000", "Fournisseurs", "C"), ("411000", "Debiteurs divers", "D"),
               ("471000", "Recettes a classer", "D"), ("512100", "Banque principale", "D"),
               ("530000", "Caisse", "D"), ("606000", "Achats non stockes", "D"),
               ("641000", "Remunerations", "D"), ("706000", "Prestations de services", "C"),
               ("740000", "Dotations", "C")]
    n, n1 = [], []
    for compte, libelle, sens in comptes:
        solde = round(rnd.uniform(5_000, 400_000), 2)
        for cible, s in ((n, solde), (n1, round(solde * rnd.uniform(0.9, 1.1), 2))):
            cible.append({"compte": compte, "libelle": libelle,
                          "solde_debiteur": s if sens == "D" else 0.0,
                          "solde_crediteur": s if sens == "C" else 0.0})
    n[1] = {**n[1], "solde_debiteur": 0.0, "solde_crediteur": 2_300.0}         # 411 créditeur
    n[5] = {**n[5], "solde_debiteur": n1[5]["solde_debiteur"] * 2.4}            # forte variation
    total_d = sum(l["solde_debiteur"] for l in n)
    total_c = sum(l["solde_crediteur"] for l in n)
    n.append({"compte": "890000", "libelle": "Equilibrage", "solde_debiteur": max(total_c - total_d, 0.0),
              "solde_crediteur": max(total_d - total_c, 0.0)})
    t1d = sum(l["solde_debiteur"] for l in n1)
    t1c = sum(l["solde_crediteur"] for l in n1)
    n1.append({"compte": "890000", "libelle": "Equilibrage", "solde_debiteur": max(t1c - t1d, 0.0),
               "solde_crediteur": max(t1d - t1c, 0.0)})
    ecrire(pd.DataFrame(n), "balance.csv")
    ecrire(pd.DataFrame(n1), "balance_n1.csv")


if __name__ == "__main__":
    DOSSIER.mkdir(exist_ok=True)
    rnd = random.Random(2026)
    rapprochement(rnd)
    fournisseurs(rnd)
    indus(rnd)
    cloture(rnd)
    print(f"Données fictives écrites dans {DOSSIER}")
