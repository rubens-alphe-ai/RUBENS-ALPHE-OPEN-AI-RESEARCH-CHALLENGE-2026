"""Contrôles des factures fournisseurs avant mise en paiement.

Chaque anomalie a un niveau :
- BLOQUANT : ne pas payer avant levée de l'anomalie ;
- ALERTE   : à examiner, le paiement reste possible.

Règles :
F1 doublon exact (même fournisseur, même numéro de facture normalisé)
F2 doublon probable (même fournisseur, même montant, dates à moins de N jours)
F3 écart avec le bon de commande, ou commande introuvable
F4 IBAN différent du référentiel ou modifié récemment (fraude au changement de RIB)
F5 IBAN invalide (clé de contrôle ISO 13616)
F6 échéance dépassée ou proche
"""

from __future__ import annotations

import re

import pandas as pd

from .lecture import convertir_date, exiger_colonnes, montants

COLONNES_FACTURES = ["fournisseur_id", "fournisseur", "numero_facture", "date_facture",
                     "date_echeance", "montant_ttc", "iban"]


def iban_valide(iban: str) -> bool:
    texte = re.sub(r"\s", "", str(iban or "")).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", texte):
        return False
    reordonne = texte[4:] + texte[:4]
    chiffres = "".join(str(int(c, 36)) for c in reordonne)
    return int(chiffres) % 97 == 1


def _normaliser_numero(numero: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(numero).upper()).lstrip("0")


def _iban(valeur) -> str:
    return re.sub(r"\s", "", str(valeur or "")).upper()


def controler_factures(
    factures: pd.DataFrame,
    date_reference: pd.Timestamp,
    commandes: pd.DataFrame | None = None,
    referentiel: pd.DataFrame | None = None,
    jours_doublon: int = 30,
    tolerance_commande: float = 0.01,
    jours_iban_recent: int = 30,
    jours_echeance_proche: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retourne (factures avec statut, anomalies)."""
    exiger_colonnes(factures, COLONNES_FACTURES, "Factures")
    f = factures.copy().reset_index(drop=True)
    montants(f, ["montant_ttc"])
    f["date_facture"] = convertir_date(f["date_facture"])
    f["date_echeance"] = convertir_date(f["date_echeance"])
    f["iban"] = f["iban"].map(_iban)
    f["num_norm"] = f["numero_facture"].map(_normaliser_numero)
    anomalies: list[dict] = []

    def ajouter(idx: int, regle: str, niveau: str, detail: str) -> None:
        ligne = f.loc[idx]
        anomalies.append({"regle": regle, "niveau": niveau, "fournisseur": ligne["fournisseur"],
                          "numero_facture": ligne["numero_facture"], "montant_ttc": ligne["montant_ttc"],
                          "detail": detail, "_idx": idx})

    # F1 doublon exact
    for _, groupe in f.groupby(["fournisseur_id", "num_norm"]):
        if len(groupe) > 1:
            for idx in groupe.index[1:]:
                ajouter(idx, "F1 doublon exact", "BLOQUANT",
                        f"Même numéro que la ligne {groupe.index[0] + 2} du fichier")

    # F2 doublon probable
    for _, groupe in f.groupby(["fournisseur_id", "montant_ttc"]):
        if len(groupe) < 2:
            continue
        g = groupe.sort_values("date_facture")
        lignes = list(g.itertuples())
        for a, b in zip(lignes, lignes[1:]):
            if a.num_norm != b.num_norm and (b.date_facture - a.date_facture).days <= jours_doublon:
                ajouter(b.Index, "F2 doublon probable", "ALERTE",
                        f"Même montant que la facture {a.numero_facture} du {a.date_facture:%d/%m/%Y}")

    # F3 commande
    if commandes is not None and "numero_commande" in f.columns:
        exiger_colonnes(commandes, ["numero_commande", "montant_ttc"], "Commandes")
        c = commandes.copy()
        montants(c, ["montant_ttc"])
        montant_cde = c.groupby(c["numero_commande"].astype(str).str.strip())["montant_ttc"].sum()
        deja_facture = f.groupby(f["numero_commande"].astype(str).str.strip())["montant_ttc"].sum()
        for idx, ligne in f.iterrows():
            num = str(ligne.get("numero_commande") or "").strip()
            if not num or num.lower() == "nan":
                ajouter(idx, "F3 commande", "ALERTE", "Facture sans numéro de commande")
            elif num not in montant_cde.index:
                ajouter(idx, "F3 commande", "BLOQUANT", f"Commande {num} introuvable")
            else:
                prevu, facture = montant_cde[num], deja_facture[num]
                if facture - prevu > max(tolerance_commande * prevu, 1.0):
                    ajouter(idx, "F3 commande", "BLOQUANT",
                            f"Facturé {facture:.2f} € pour une commande de {prevu:.2f} €")

    # F4 IBAN vs référentiel
    if referentiel is not None:
        exiger_colonnes(referentiel, ["fournisseur_id", "iban"], "Référentiel fournisseurs")
        ref = referentiel.copy()
        ref["iban"] = ref["iban"].map(_iban)
        if "date_modif_iban" in ref.columns:
            ref["date_modif_iban"] = convertir_date(ref["date_modif_iban"].fillna("1900-01-01"))
        ref = ref.drop_duplicates("fournisseur_id", keep="last").set_index("fournisseur_id")
        for idx, ligne in f.iterrows():
            fid = ligne["fournisseur_id"]
            if fid not in ref.index:
                ajouter(idx, "F4 IBAN", "BLOQUANT", "Fournisseur absent du référentiel")
                continue
            attendu = ref.loc[fid]
            if ligne["iban"] != attendu["iban"]:
                ajouter(idx, "F4 IBAN", "BLOQUANT",
                        "IBAN de la facture différent du référentiel : contre-appeler le fournisseur "
                        "à un numéro connu avant tout paiement")
            elif "date_modif_iban" in ref.columns:
                modif = attendu["date_modif_iban"]
                if (date_reference - modif).days <= jours_iban_recent:
                    ajouter(idx, "F4 IBAN", "ALERTE",
                            f"IBAN modifié le {modif:%d/%m/%Y} : vérifier la procédure de changement")

    # F5 IBAN invalide
    for idx, ligne in f.iterrows():
        if not iban_valide(ligne["iban"]):
            ajouter(idx, "F5 IBAN invalide", "BLOQUANT", f"Clé IBAN incorrecte : {ligne['iban']}")

    # F6 échéances
    for idx, ligne in f.iterrows():
        jours = (ligne["date_echeance"] - date_reference).days
        if jours < 0:
            ajouter(idx, "F6 échéance", "ALERTE",
                    f"Échéance dépassée de {-jours} jour(s) : risque d'intérêts moratoires")
        elif jours <= jours_echeance_proche:
            ajouter(idx, "F6 échéance", "ALERTE", f"Échéance dans {jours} jour(s)")

    df_anom = pd.DataFrame(anomalies, columns=["regle", "niveau", "fournisseur", "numero_facture",
                                               "montant_ttc", "detail", "_idx"])
    bloquees = set(df_anom.loc[df_anom["niveau"] == "BLOQUANT", "_idx"])
    alertes = set(df_anom.loc[df_anom["niveau"] == "ALERTE", "_idx"])
    f["statut"] = ["BLOQUÉE" if i in bloquees else "À EXAMINER" if i in alertes else "PRÊTE"
                   for i in f.index]
    f = f.drop(columns=["num_norm"]).sort_values(["statut", "date_echeance"])
    df_anom = df_anom.drop(columns=["_idx"]).sort_values(["niveau", "regle"], ascending=[False, True])
    return f, df_anom
