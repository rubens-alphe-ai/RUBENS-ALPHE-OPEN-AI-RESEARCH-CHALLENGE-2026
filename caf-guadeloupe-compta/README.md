# compta_auto — aide à l'automatisation de l'agence comptable

Prototype d'outils pour la CAF de la Guadeloupe. Ils **lisent des exports**
(MAGIC, SID, relevés bancaires, tableurs), **contrôlent** et **proposent**.
Ils ne passent aucune écriture et ne déclenchent aucun paiement : un agent
habilité valide chaque proposition.

| Traitement | Entrées | Ce que produit le rapport Excel |
| --- | --- | --- |
| `rapprochement` | relevé bancaire, grand livre du compte 512 | lettrages (3 niveaux de confiance), relevé non lettré, écritures en suspens, synthèse de l'écart |
| `fournisseurs` | factures ; commandes et référentiel fournisseurs facultatifs | statut par facture (PRÊTE / À EXAMINER / BLOQUÉE), anomalies F1–F6 |
| `indus` | créances ; échéancier facultatif | balance âgée, échéances en retard, relances priorisées |
| `cloture` | balance ; balance N-1 facultative | équilibre, soldes de sens anormal, comptes d'attente, variations fortes |

Chaque rapport contient un onglet **Piste d'audit** : date, utilisateur, poste,
version, empreinte SHA-256 de chaque fichier d'entrée et paramètres.

## Installation

Python 3.10 ou plus récent.

```
pip install -r requirements.txt
```

## Essai sur données fictives

```
python exemples/generer_donnees.py
python -m compta_auto rapprochement --releve exemples/donnees/releve_bancaire.csv --grand-livre exemples/donnees/grand_livre_512.csv
python -m compta_auto fournisseurs --factures exemples/donnees/factures.csv --commandes exemples/donnees/commandes.csv --referentiel exemples/donnees/referentiel_fournisseurs.csv --date-reference 31/10/2026
python -m compta_auto indus --creances exemples/donnees/creances_indus.csv --echeancier exemples/donnees/echeancier_indus.csv --date-reference 31/10/2026
python -m compta_auto cloture --balance exemples/donnees/balance.csv --balance-n1 exemples/donnees/balance_n1.csv
```

`--sortie fichier.xlsx` choisit le nom du rapport.

## Format des fichiers

CSV (séparateur `;` ou `,`, UTF-8 ou Windows-1252) ou Excel. Les noms de
colonnes sont comparés sans accents ni majuscules (`Libellé` = `libelle`).
Montants `1 234,56` ou `1234.56`, dates `jj/mm/aaaa` ou `aaaa-mm-jj`.

| Fichier | Colonnes obligatoires | Facultatives |
| --- | --- | --- |
| Relevé bancaire | `date`, `libelle`, `montant` (crédit > 0) | `reference` |
| Grand livre 512 | `date`, `piece`, `libelle`, `debit`, `credit` | `reference` |
| Factures | `fournisseur_id`, `fournisseur`, `numero_facture`, `date_facture`, `date_echeance`, `montant_ttc`, `iban` | `numero_commande` |
| Commandes | `numero_commande`, `montant_ttc` | |
| Référentiel fournisseurs | `fournisseur_id`, `iban` | `date_modif_iban` |
| Créances (indus) | `numero_dossier`, `date_constat`, `montant_initial`, `montant_recouvre` | |
| Échéancier | `numero_dossier`, `date_echeance`, `montant_prevu`, `montant_paye` | |
| Balance | `compte`, `libelle`, `solde_debiteur`, `solde_crediteur` | |

Les exports réels n'auront pas exactement ces noms : renommer les colonnes
dans Excel, ou ajouter une correspondance dans `compta_auto/lecture.py`
une fois les formats MAGIC / SID connus.

## Points à adapter avant usage réel

- `SENS_NORMAL` et `PREFIXES_ATTENTE` dans `cloture.py` : à aligner sur le PCUOSS
  et la nomenclature locale.
- Seuils (tolérance de date, délai de doublon, seuil d'ancienneté des indus,
  seuils de variation) : à fixer avec l'agent comptable.
- Données personnelles : utiliser des identifiants de dossier internes, jamais
  de nom ni de NIR ; exécuter sur un poste interne ; déclarer le traitement au DPO.

## Tests

```
python -m unittest discover -s tests
```
