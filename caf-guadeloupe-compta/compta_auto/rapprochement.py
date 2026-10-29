"""Rapprochement bancaire : relevé de banque contre compte 512 du grand livre.

Conventions :
- relevé : `montant` signé du point de vue de la banque (crédit > 0) ;
- grand livre : `debit` / `credit` du compte 512 ; un débit en
  comptabilité correspond à un crédit sur le relevé.

Trois passes, de la plus sûre à la moins sûre ; chaque ligne n'est
lettrée qu'une fois :
1. même référence et même montant            (confiance HAUTE)
2. même montant, date à ± N jours, la plus proche (confiance MOYENNE)
3. une ligne de relevé égale à la somme des écritures
   d'un même jour (remise groupée)            (confiance A_VERIFIER)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .lecture import convertir_date, exiger_colonnes, montants

COLONNES_RELEVE = ["date", "libelle", "montant"]
COLONNES_GRAND_LIVRE = ["date", "piece", "libelle", "debit", "credit"]


@dataclass
class ResultatRapprochement:
    lettrages: pd.DataFrame
    releve_non_lettre: pd.DataFrame
    compta_non_lettree: pd.DataFrame
    synthese: pd.DataFrame


def preparer(releve: pd.DataFrame, grand_livre: pd.DataFrame):
    exiger_colonnes(releve, COLONNES_RELEVE, "Relevé bancaire")
    exiger_colonnes(grand_livre, COLONNES_GRAND_LIVRE, "Grand livre 512")
    releve = releve.copy().reset_index(drop=True)
    gl = grand_livre.copy().reset_index(drop=True)
    montants(releve, ["montant"])
    montants(gl, ["debit", "credit"])
    releve["date"] = convertir_date(releve["date"])
    gl["date"] = convertir_date(gl["date"])
    gl["montant"] = (gl["debit"] - gl["credit"]).round(2)
    for df in (releve, gl):
        if "reference" not in df.columns:
            df["reference"] = ""
        df["reference"] = df["reference"].fillna("").astype(str).str.strip().str.upper()
    releve["id_releve"] = releve.index
    gl["id_compta"] = gl.index
    return releve, gl


def rapprocher(releve: pd.DataFrame, grand_livre: pd.DataFrame, tolerance_jours: int = 3) -> ResultatRapprochement:
    releve, gl = preparer(releve, grand_livre)
    libres_r = set(releve["id_releve"])
    libres_c = set(gl["id_compta"])
    lettrages: list[dict] = []

    def lettrer(ids_r: list[int], ids_c: list[int], methode: str, confiance: str) -> None:
        code = f"L{len(lettrages) + 1:05d}"
        for i in ids_r:
            libres_r.discard(i)
        for j in ids_c:
            libres_c.discard(j)
        lettrages.append({
            "code_lettrage": code,
            "methode": methode,
            "confiance": confiance,
            "ids_releve": ids_r,
            "ids_compta": ids_c,
        })

    # Passe 1 : référence + montant
    avec_ref = gl[gl["reference"] != ""]
    index_ref = {}
    for j, ref, mt in zip(avec_ref["id_compta"], avec_ref["reference"], avec_ref["montant"]):
        index_ref.setdefault((ref, mt), []).append(j)
    for i, ref, mt in zip(releve["id_releve"], releve["reference"], releve["montant"]):
        if not ref:
            continue
        candidats = [j for j in index_ref.get((ref, mt), []) if j in libres_c]
        if candidats:
            lettrer([i], [candidats[0]], "reference+montant", "HAUTE")

    # Passe 2 : montant + date la plus proche dans la tolérance
    for i in sorted(libres_r):
        r = releve.loc[i]
        cand = gl[gl["id_compta"].isin(libres_c) & (gl["montant"] == r["montant"])]
        if cand.empty:
            continue
        ecart = (cand["date"] - r["date"]).abs().dt.days
        cand = cand[ecart <= tolerance_jours]
        if cand.empty:
            continue
        j = int(cand.assign(ecart=ecart).sort_values(["ecart", "id_compta"]).iloc[0]["id_compta"])
        lettrer([i], [j], f"montant+date(±{tolerance_jours}j)", "MOYENNE")

    # Passe 3 : remise groupée (somme des écritures d'un même jour)
    restant_c = gl[gl["id_compta"].isin(libres_c)]
    sommes = restant_c.groupby("date")["montant"].agg(["sum", "count"]).reset_index()
    sommes = sommes[sommes["count"] > 1]
    for i in sorted(libres_r):
        r = releve.loc[i]
        ecart = (sommes["date"] - r["date"]).abs().dt.days
        cand = sommes[(sommes["sum"].round(2) == r["montant"]) & (ecart <= tolerance_jours)]
        if cand.empty:
            continue
        jour = cand.iloc[0]["date"]
        ids_c = [int(j) for j in restant_c.loc[restant_c["date"] == jour, "id_compta"] if j in libres_c]
        if len(ids_c) > 1 and round(gl.loc[ids_c, "montant"].sum(), 2) == r["montant"]:
            lettrer([i], ids_c, "remise_groupee", "A_VERIFIER")
            sommes = sommes[sommes["date"] != jour]

    lignes = []
    for l in lettrages:
        for i in l["ids_releve"]:
            r = releve.loc[i]
            lignes.append({**_meta(l), "source": "releve", "date": r["date"], "piece": "",
                           "libelle": r["libelle"], "montant": r["montant"]})
        for j in l["ids_compta"]:
            c = gl.loc[j]
            lignes.append({**_meta(l), "source": "compta", "date": c["date"], "piece": c["piece"],
                           "libelle": c["libelle"], "montant": c["montant"]})
    df_lettrages = pd.DataFrame(lignes, columns=["code_lettrage", "methode", "confiance", "source",
                                                 "date", "piece", "libelle", "montant"])

    r_nl = releve[releve["id_releve"].isin(libres_r)].drop(columns=["id_releve"])
    c_nl = gl[gl["id_compta"].isin(libres_c)].drop(columns=["id_compta"])
    r_nl = r_nl.assign(action="À comptabiliser ou à justifier (frais, rejet, virement non identifié)")
    c_nl = c_nl.assign(action="En suspens : vérifier passage en banque (chèque non encaissé, virement en cours)")

    solde_releve = round(releve["montant"].sum(), 2)
    solde_compta = round(gl["montant"].sum(), 2)
    synthese = pd.DataFrame([
        ("Lignes de relevé", len(releve)),
        ("Lignes de relevé lettrées", len(releve) - len(r_nl)),
        ("Taux de lettrage relevé (%)", round(100 * (len(releve) - len(r_nl)) / max(len(releve), 1), 1)),
        ("Écritures 512", len(gl)),
        ("Écritures 512 lettrées", len(gl) - len(c_nl)),
        ("Mouvements relevé (€)", solde_releve),
        ("Mouvements compta 512 (€)", solde_compta),
        ("Écart (€)", round(solde_releve - solde_compta, 2)),
        ("Écart expliqué par les non-lettrés (€)",
         round(r_nl["montant"].sum() - c_nl["montant"].sum(), 2)),
        ("Lettrages à vérifier (remises groupées)",
         sum(1 for l in lettrages if l["confiance"] == "A_VERIFIER")),
    ], columns=["indicateur", "valeur"])

    return ResultatRapprochement(df_lettrages, r_nl, c_nl, synthese)


def _meta(l: dict) -> dict:
    return {"code_lettrage": l["code_lettrage"], "methode": l["methode"], "confiance": l["confiance"]}
