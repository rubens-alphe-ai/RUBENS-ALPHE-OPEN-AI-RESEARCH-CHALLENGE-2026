"""Ligne de commande : python -m compta_auto <traitement> ...

Exemples :
    python -m compta_auto rapprochement --releve releve.csv --grand-livre gl512.csv
    python -m compta_auto fournisseurs --factures factures.csv --commandes commandes.csv \
        --referentiel fournisseurs.csv
    python -m compta_auto indus --creances creances.csv --echeancier echeancier.csv
    python -m compta_auto cloture --balance balance.csv --balance-n1 balance_n1.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from .cloture import controler_balance
from .fournisseurs import controler_factures
from .indus import analyser_indus
from .lecture import ColonnesManquantes, lire_table
from .rapport import ecrire_rapport
from .rapprochement import rapprocher


def _date(texte: str) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(texte, dayfirst=True))


def _sortie(args, prefixe: str) -> str:
    return args.sortie or f"{prefixe}_{date.today():%Y%m%d}.xlsx"


def cmd_rapprochement(args) -> str:
    res = rapprocher(lire_table(args.releve), lire_table(args.grand_livre), args.tolerance_jours)
    print(res.synthese.to_string(index=False))
    return ecrire_rapport(
        _sortie(args, "rapprochement"),
        {"Synthèse": res.synthese, "Lettrages": res.lettrages,
         "Relevé non lettré": res.releve_non_lettre, "Compta non lettrée": res.compta_non_lettree},
        "Rapprochement bancaire", {"relevé": args.releve, "grand livre": args.grand_livre},
        {"tolérance (jours)": args.tolerance_jours})


def cmd_fournisseurs(args) -> str:
    factures, anomalies = controler_factures(
        lire_table(args.factures), args.date_reference,
        lire_table(args.commandes) if args.commandes else None,
        lire_table(args.referentiel) if args.referentiel else None)
    print(factures["statut"].value_counts().to_string())
    return ecrire_rapport(
        _sortie(args, "controle_factures"), {"Anomalies": anomalies, "Factures": factures},
        "Contrôle des factures avant paiement",
        {"factures": args.factures, "commandes": args.commandes, "référentiel": args.referentiel},
        {"date de référence": args.date_reference.date()})


def cmd_indus(args) -> str:
    res = analyser_indus(lire_table(args.creances), args.date_reference,
                         lire_table(args.echeancier) if args.echeancier else None)
    print(res["balance_agee"].to_string(index=False))
    return ecrire_rapport(
        _sortie(args, "suivi_indus"),
        {"Balance âgée": res["balance_agee"], "Relances": res["relances"],
         "Échéances en retard": res["echeances_en_retard"], "Créances ouvertes": res["creances_ouvertes"]},
        "Suivi des indus", {"créances": args.creances, "échéancier": args.echeancier},
        {"date de référence": args.date_reference.date()})


def cmd_cloture(args) -> str:
    res = controler_balance(lire_table(args.balance),
                            lire_table(args.balance_n1) if args.balance_n1 else None)
    print(res["synthese"].to_string(index=False))
    onglets = {"Synthèse": res["synthese"], "Constats": res["constats"]}
    if not res["variations"].empty:
        onglets["Variations N-1"] = res["variations"]
    return ecrire_rapport(_sortie(args, "controles_cloture"), onglets, "Contrôles de clôture",
                          {"balance": args.balance, "balance N-1": args.balance_n1}, {})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="compta_auto", description="Aide à l'automatisation comptable")
    sp = p.add_subparsers(dest="traitement", required=True)

    r = sp.add_parser("rapprochement", help="Rapprochement bancaire relevé / compte 512")
    r.add_argument("--releve", required=True)
    r.add_argument("--grand-livre", required=True)
    r.add_argument("--tolerance-jours", type=int, default=3)
    r.set_defaults(func=cmd_rapprochement)

    f = sp.add_parser("fournisseurs", help="Contrôle des factures avant paiement")
    f.add_argument("--factures", required=True)
    f.add_argument("--commandes")
    f.add_argument("--referentiel")
    f.set_defaults(func=cmd_fournisseurs)

    i = sp.add_parser("indus", help="Balance âgée et relances des indus")
    i.add_argument("--creances", required=True)
    i.add_argument("--echeancier")
    i.set_defaults(func=cmd_indus)

    c = sp.add_parser("cloture", help="Contrôles de balance avant clôture")
    c.add_argument("--balance", required=True)
    c.add_argument("--balance-n1")
    c.set_defaults(func=cmd_cloture)

    for sous in (r, f, i, c):
        sous.add_argument("--sortie", help="Fichier Excel produit")
    for sous in (f, i):
        sous.add_argument("--date-reference", type=_date, default=pd.Timestamp(date.today()),
                          help="jj/mm/aaaa (défaut : aujourd'hui)")

    args = p.parse_args(argv)
    try:
        chemin = args.func(args)
    except ColonnesManquantes as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    print(f"\nRapport écrit : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
