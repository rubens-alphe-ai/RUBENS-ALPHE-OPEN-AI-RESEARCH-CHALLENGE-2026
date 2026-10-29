"""Contrôles de clôture sur la balance générale.

Balance attendue : compte, libelle, solde_debiteur, solde_crediteur.
Balance N-1 facultative, même format, pour les variations.

Les règles de sens sont un point de départ inspiré du plan comptable
général : elles sont à ajuster au plan comptable unique des organismes
de sécurité sociale (PCUOSS) et à la nomenclature locale.
"""

from __future__ import annotations

import pandas as pd

from .lecture import exiger_colonnes, montants

COLONNES_BALANCE = ["compte", "libelle", "solde_debiteur", "solde_crediteur"]

# préfixe de compte -> sens normal du solde ("D" ou "C")
SENS_NORMAL = {
    "512": "D",   # banques : un solde créditeur signale un découvert
    "53": "D",    # caisse : jamais créditrice
    "401": "C",   # fournisseurs
    "411": "D",   # débiteurs / clients
    "6": "D",     # charges
    "7": "C",     # produits
}

PREFIXES_ATTENTE = ("471", "472", "473", "474", "475", "476", "477", "478")


def _sens_attendu(compte: str) -> str | None:
    meilleur = None
    for prefixe, sens in SENS_NORMAL.items():
        if compte.startswith(prefixe) and (meilleur is None or len(prefixe) > len(meilleur[0])):
            meilleur = (prefixe, sens)
    return meilleur[1] if meilleur else None


def _preparer(balance: pd.DataFrame, nom: str) -> pd.DataFrame:
    exiger_colonnes(balance, COLONNES_BALANCE, nom)
    b = balance.copy()
    montants(b, ["solde_debiteur", "solde_crediteur"])
    b["compte"] = b["compte"].astype(str).str.strip()
    b["solde"] = (b["solde_debiteur"] - b["solde_crediteur"]).round(2)
    return b


def controler_balance(
    balance: pd.DataFrame,
    balance_n1: pd.DataFrame | None = None,
    seuil_variation_pct: float = 50.0,
    seuil_variation_montant: float = 10_000.0,
) -> dict[str, pd.DataFrame]:
    b = _preparer(balance, "Balance")
    constats: list[dict] = []

    total_d, total_c = round(b["solde_debiteur"].sum(), 2), round(b["solde_crediteur"].sum(), 2)
    if abs(total_d - total_c) > 0.005:
        constats.append({"controle": "C1 équilibre", "niveau": "BLOQUANT", "compte": "",
                         "libelle": "", "solde": round(total_d - total_c, 2),
                         "detail": f"Débits {total_d:,.2f} € ≠ crédits {total_c:,.2f} €"})

    for _, l in b.iterrows():
        sens = _sens_attendu(l["compte"])
        if (sens == "D" and l["solde"] < 0) or (sens == "C" and l["solde"] > 0):
            constats.append({"controle": "C2 sens anormal", "niveau": "ALERTE", "compte": l["compte"],
                             "libelle": l["libelle"], "solde": l["solde"],
                             "detail": f"Solde {'créditeur' if l['solde'] < 0 else 'débiteur'} "
                                       f"sur un compte normalement {'débiteur' if sens == 'D' else 'créditeur'}"})
        if l["compte"].startswith(PREFIXES_ATTENTE) and l["solde"] != 0:
            constats.append({"controle": "C3 compte d'attente", "niveau": "ALERTE", "compte": l["compte"],
                             "libelle": l["libelle"], "solde": l["solde"],
                             "detail": "Compte d'attente non apuré : justifier ou reclasser avant clôture"})

    variations = pd.DataFrame()
    if balance_n1 is not None:
        n1 = _preparer(balance_n1, "Balance N-1")[["compte", "solde"]].rename(columns={"solde": "solde_n1"})
        variations = b[["compte", "libelle", "solde"]].merge(n1, on="compte", how="outer")
        variations[["solde", "solde_n1"]] = variations[["solde", "solde_n1"]].fillna(0.0)
        variations["variation"] = (variations["solde"] - variations["solde_n1"]).round(2)
        variations["variation_%"] = (100 * variations["variation"]
                                     / variations["solde_n1"].abs().where(variations["solde_n1"] != 0)).round(1)
        fortes = variations[(variations["variation"].abs() >= seuil_variation_montant)
                            & ((variations["variation_%"].abs() >= seuil_variation_pct)
                               | variations["variation_%"].isna())]
        for _, l in fortes.iterrows():
            pct = "nouveau compte" if pd.isna(l["variation_%"]) else f"{l['variation_%']:+.1f} %"
            constats.append({"controle": "C4 variation", "niveau": "ALERTE", "compte": l["compte"],
                             "libelle": l["libelle"], "solde": l["solde"],
                             "detail": f"Variation {l['variation']:+,.2f} € ({pct}) : à commenter"})

    synthese = pd.DataFrame([
        ("Comptes", len(b)),
        ("Total débits (€)", total_d),
        ("Total crédits (€)", total_c),
        ("Constats bloquants", sum(c["niveau"] == "BLOQUANT" for c in constats)),
        ("Constats en alerte", sum(c["niveau"] == "ALERTE" for c in constats)),
    ], columns=["indicateur", "valeur"])

    return {"synthese": synthese,
            "constats": pd.DataFrame(constats, columns=["controle", "niveau", "compte", "libelle",
                                                        "solde", "detail"]),
            "variations": variations}
