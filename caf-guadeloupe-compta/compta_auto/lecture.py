"""Lecture et normalisation des exports comptables (CSV ou Excel).

Les exports des applicatifs sont souvent en CSV « à la française » :
séparateur point-virgule, encodage Windows-1252, montants « 1 234,56 »
et dates « 31/12/2026 ». Ce module absorbe ces variations pour que les
contrôles travaillent sur des colonnes typées et nommées de façon stable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd


class ColonnesManquantes(ValueError):
    """Un fichier ne contient pas les colonnes attendues."""


def normaliser_nom(nom: str) -> str:
    """'Libellé opération' -> 'libelle_operation'."""
    sans_accent = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accent.lower()).strip("_")


def lire_table(chemin: str | Path) -> pd.DataFrame:
    """Lit un CSV (séparateur et encodage détectés) ou un fichier Excel.

    Toutes les cellules sont lues comme du texte : la conversion des
    montants et des dates est faite explicitement par les appelants.
    """
    chemin = Path(chemin)
    if chemin.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(chemin, dtype=str)
    else:
        df = None
        for encodage in ("utf-8-sig", "cp1252"):
            try:
                df = pd.read_csv(chemin, sep=None, engine="python", dtype=str, encoding=encodage)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError(f"Encodage non reconnu : {chemin}")
    df.columns = [normaliser_nom(c) for c in df.columns]
    return df.dropna(how="all")


def exiger_colonnes(df: pd.DataFrame, colonnes: list[str], fichier: str) -> None:
    manquantes = [c for c in colonnes if c not in df.columns]
    if manquantes:
        raise ColonnesManquantes(
            f"{fichier} : colonnes manquantes {manquantes}. "
            f"Colonnes trouvées : {list(df.columns)}"
        )


def convertir_montant(valeur) -> float:
    """Accepte 1234.56, '1 234,56', '1.234,56', '-12,5 €', '' (-> 0)."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    texte = str(valeur).replace(" ", "").replace(" ", "").replace(" ", "").replace("€", "")
    if not texte:
        return 0.0
    if "," in texte and "." in texte:
        texte = texte.replace(".", "").replace(",", ".")
    elif "," in texte:
        texte = texte.replace(",", ".")
    return float(texte)


def convertir_date(serie: pd.Series) -> pd.Series:
    """Dates jj/mm/aaaa ou aaaa-mm-jj ; une date illisible lève une erreur."""
    texte = serie.astype(str).str.strip()
    iso = texte.str.match(r"^\d{4}-\d{2}-\d{2}")
    resultat = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    resultat[iso] = pd.to_datetime(texte[iso].str[:10], format="%Y-%m-%d")
    resultat[~iso] = pd.to_datetime(texte[~iso], format="%d/%m/%Y")
    return resultat


def montants(df: pd.DataFrame, colonnes: list[str]) -> None:
    for c in colonnes:
        if c in df.columns:
            df[c] = df[c].map(convertir_montant).round(2)


def empreinte(chemin: str | Path) -> str:
    """SHA-256 du fichier, pour la piste d'audit."""
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()
