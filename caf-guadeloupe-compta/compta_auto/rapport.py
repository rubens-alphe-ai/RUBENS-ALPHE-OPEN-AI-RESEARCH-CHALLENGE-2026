"""Écriture des rapports Excel, avec un onglet « Piste d'audit »."""

from __future__ import annotations

import getpass
import platform
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import __version__
from .lecture import empreinte


def ecrire_rapport(
    sortie: str | Path,
    onglets: dict[str, pd.DataFrame],
    traitement: str,
    fichiers_entree: dict[str, str | Path],
    parametres: dict,
) -> Path:
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    audit = [
        ("Traitement", traitement),
        ("Version de l'outil", __version__),
        ("Exécuté le", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        ("Exécuté par", getpass.getuser()),
        ("Poste", platform.node()),
    ]
    for nom, chemin in fichiers_entree.items():
        if chemin:
            audit.append((f"Fichier {nom}", str(chemin)))
            audit.append((f"SHA-256 {nom}", empreinte(chemin)))
    for cle, valeur in parametres.items():
        audit.append((f"Paramètre {cle}", str(valeur)))
    audit.append(("Avertissement", "Propositions automatiques : validation par un agent habilité requise."))

    with pd.ExcelWriter(sortie, engine="openpyxl", datetime_format="DD/MM/YYYY", date_format="DD/MM/YYYY") as xl:
        for nom, df in onglets.items():
            df.to_excel(xl, sheet_name=nom[:31], index=False)
        pd.DataFrame(audit, columns=["élément", "valeur"]).to_excel(xl, sheet_name="Piste d'audit", index=False)
        for feuille in xl.book.worksheets:
            feuille.freeze_panes = "A2"
            for colonne in feuille.columns:
                largeur = max(len(str(c.value or "")) for c in colonne)
                feuille.column_dimensions[colonne[0].column_letter].width = min(max(largeur + 2, 10), 70)
    return sortie
