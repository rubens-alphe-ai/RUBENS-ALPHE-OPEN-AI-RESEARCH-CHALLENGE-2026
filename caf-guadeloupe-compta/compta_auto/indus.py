"""Suivi des indus : balance âgée, échéanciers en retard, relances priorisées.

Fichier des créances (une ligne par indu) :
    numero_dossier, date_constat, montant_initial, montant_recouvre
Fichier des échéanciers (facultatif, une ligne par échéance) :
    numero_dossier, date_echeance, montant_prevu, montant_paye

`numero_dossier` doit être un identifiant interne : ni nom, ni NIR
dans les fichiers manipulés par l'outil.
"""

from __future__ import annotations

import pandas as pd

from .lecture import convertir_date, exiger_colonnes, montants

COLONNES_CREANCES = ["numero_dossier", "date_constat", "montant_initial", "montant_recouvre"]
COLONNES_ECHEANCIER = ["numero_dossier", "date_echeance", "montant_prevu", "montant_paye"]

TRANCHES = [(0, 90, "0-3 mois"), (91, 182, "3-6 mois"), (183, 365, "6-12 mois"),
            (366, 730, "1-2 ans"), (731, 10**6, "> 2 ans")]


def _tranche(jours: int) -> str:
    for debut, fin, libelle in TRANCHES:
        if debut <= jours <= fin:
            return libelle
    return "date future"


def analyser_indus(
    creances: pd.DataFrame,
    date_reference: pd.Timestamp,
    echeancier: pd.DataFrame | None = None,
    jours_alerte_anciennete: int = 540,
) -> dict[str, pd.DataFrame]:
    exiger_colonnes(creances, COLONNES_CREANCES, "Créances")
    c = creances.copy()
    montants(c, ["montant_initial", "montant_recouvre"])
    c["date_constat"] = convertir_date(c["date_constat"])
    c["solde"] = (c["montant_initial"] - c["montant_recouvre"]).round(2)
    c["anciennete_jours"] = (date_reference - c["date_constat"]).dt.days
    c["tranche"] = c["anciennete_jours"].map(_tranche)
    ouvertes = c[c["solde"] > 0].copy()

    ordre = [t[2] for t in TRANCHES]
    balance = (ouvertes.groupby("tranche")
               .agg(nombre=("solde", "size"), solde=("solde", "sum"))
               .reindex(ordre, fill_value=0).reset_index())
    balance["part_%"] = (100 * balance["solde"] / max(balance["solde"].sum(), 0.01)).round(1)
    balance.loc[len(balance)] = ["TOTAL", balance["nombre"].sum(), round(balance["solde"].sum(), 2), 100.0]

    retards = pd.DataFrame(columns=["numero_dossier", "echeances_impayees", "montant_impaye",
                                    "plus_ancienne_impayee"])
    if echeancier is not None:
        exiger_colonnes(echeancier, COLONNES_ECHEANCIER, "Échéancier")
        e = echeancier.copy()
        montants(e, ["montant_prevu", "montant_paye"])
        e["date_echeance"] = convertir_date(e["date_echeance"])
        e["impaye"] = (e["montant_prevu"] - e["montant_paye"]).clip(lower=0).round(2)
        e = e[(e["date_echeance"] < date_reference) & (e["impaye"] > 0)]
        retards = (e.groupby("numero_dossier")
                   .agg(echeances_impayees=("impaye", "size"), montant_impaye=("impaye", "sum"),
                        plus_ancienne_impayee=("date_echeance", "min"))
                   .reset_index())

    relances = ouvertes.merge(retards, on="numero_dossier", how="left")
    relances["echeances_impayees"] = relances["echeances_impayees"].fillna(0).astype(int)
    relances["montant_impaye"] = relances["montant_impaye"].fillna(0.0)
    relances["motif"] = relances.apply(_motif, axis=1, args=(jours_alerte_anciennete,))
    relances = relances[relances["motif"] != ""]
    relances["priorite"] = relances.apply(_priorite, axis=1, args=(jours_alerte_anciennete,))
    relances = relances.sort_values(["priorite", "solde"], ascending=[True, False])
    relances = relances[["priorite", "numero_dossier", "solde", "anciennete_jours",
                         "echeances_impayees", "montant_impaye", "motif"]]

    return {"balance_agee": balance, "echeances_en_retard": retards,
            "relances": relances, "creances_ouvertes": ouvertes}


def _motif(ligne, seuil: int) -> str:
    motifs = []
    if ligne["echeances_impayees"] > 0:
        motifs.append(f"{ligne['echeances_impayees']} échéance(s) impayée(s)")
    if ligne["anciennete_jours"] >= seuil:
        motifs.append("ancienneté élevée : vérifier les actes interruptifs de prescription")
    if ligne["montant_recouvre"] == 0 and ligne["anciennete_jours"] > 60:
        motifs.append("aucun recouvrement depuis le constat")
    return " ; ".join(motifs)


def _priorite(ligne, seuil: int) -> int:
    if ligne["anciennete_jours"] >= seuil:
        return 1
    if ligne["echeances_impayees"] >= 2:
        return 2
    return 3
