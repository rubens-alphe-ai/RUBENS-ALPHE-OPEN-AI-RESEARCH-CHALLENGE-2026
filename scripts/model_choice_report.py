#!/usr/bin/env python3
"""Write the "verified model choice" deliverable: which differences between candidate models are real.

Input: per-item results (trial,item,correct) for up to five candidate models on
the same items, and optionally their list prices. Output: a self-contained
French HTML report that a buyer can read without a statistician:

- each model's score with its 95% interval;
- every pair compared on the items both answered (exact McNemar), with the gap
  and its 95% interval;
- the leading group: the models not shown to be behind the best one;
- the items that decide: how many give every candidate the same result;
- a reading that never turns "not shown different" into "equal".

  python scripts/model_choice_report.py --table results.csv --models a,b,c,d,e \\
      --prices prices.json --title "..." --out report.html
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claim_check import compare  # noqa: E402
from compress_benchmark import load_table  # noqa: E402
from validate_against_redux import wilson  # noqa: E402


def pct(x: float, d: int = 1) -> str:
    return (("%." + str(d) + "f") % (100 * x)).replace(".", ",")


def fr(x: float, d: int = 1) -> str:
    return (("%." + str(d) + "f") % x).replace(".", ",")


def sfr(x: float) -> str:
    return ("+" if x > 0 else "") + fr(x)


def analyse(by: dict, models: list[str]) -> dict:
    items = sorted(set.intersection(*(set(by[m]) for m in models)))
    scores = {m: sum(by[m][i] for i in items) / len(items) for m in models}
    order = sorted(models, key=lambda m: -scores[m])
    pairs = []
    for x in range(len(order)):
        for y in range(x + 1, len(order)):
            a, b = order[x], order[y]
            r = compare({i: by[a][i] for i in items}, {i: by[b][i] for i in items})
            pairs.append({"a": a, "b": b, **r})
    best = order[0]
    leading = [best] + [p["b"] for p in pairs if p["a"] == best and not p["supported_at_95"]]
    same = sum(1 for i in items if len({by[m][i] for m in models}) == 1)
    all_right = sum(1 for i in items if all(by[m][i] == 1 for m in models))
    return {"items": items, "scores": scores, "order": order, "pairs": pairs, "leading": leading,
            "same_result": same, "all_right": all_right, "all_wrong": same - all_right}


def render(title: str, source: str, models: list[str], labels: dict, prices: dict, a: dict) -> str:
    n = len(a["items"])
    esc = html.escape

    def name(m: str) -> str:
        return esc(labels.get(m, m))

    best = a["order"][0]
    rows = []
    for m in a["order"]:
        k = round(a["scores"][m] * n)
        lo, hi = wilson(k, n)
        price = prices.get(m)
        rows.append("<tr><td>%s</td><td class=num>%s %%</td><td class=num>%s – %s %%</td><td class=num>%s</td></tr>"
                    % (name(m), pct(a["scores"][m]), pct(lo), pct(hi),
                       "%s $ / %s $" % (fr(price[0], 2), fr(price[1], 2)) if price else "—"))
    prow = []
    for p in a["pairs"]:
        lo, hi = p["gap_interval_95_pts"]
        verdict = ("<span class=ok>écart établi</span>" if p["supported_at_95"]
                   else "<span class=no>écart non établi</span>")
        prow.append("<tr><td>%s</td><td>%s</td><td class=num>%s</td><td class=num>[%s ; %s]</td>"
                    "<td class=num>%s</td><td class=num>%d / %d</td><td>%s</td></tr>"
                    % (name(p["a"]), name(p["b"]), sfr(p["gap_pts"]), sfr(lo), sfr(hi),
                       ("< 0,001" if p["mcnemar_exact_p"] < 0.001 else fr(p["mcnemar_exact_p"], 3)),
                       p["items_only_a_right"], p["items_only_b_right"], verdict))
    leading = a["leading"]
    others = [m for m in a["order"] if m not in leading]
    priced_leading = [m for m in leading if m in prices]
    cheapest = min(priced_leading, key=lambda m: prices[m][1]) if priced_leading else None
    summary = ["<li><strong>%s</strong> a le meilleur score sur ces %d tâches (%s %%).</li>" % (name(best), n, pct(a["scores"][best]))]
    if len(leading) > 1:
        summary.append("<li><strong>Groupe de tête :</strong> %s. Aucun de ces modèles n'est démontré moins bon que %s "
                       "sur ces tâches : les écarts observés restent dans le bruit statistique.</li>"
                       % (", ".join(name(m) for m in leading), name(best)))
    if others:
        summary.append("<li><strong>Démontrés en dessous du meilleur :</strong> %s.</li>" % ", ".join(name(m) for m in others))
        second = others[0]
        group2 = [second] + [p["b"] for p in a["pairs"] if p["a"] == second and p["b"] in others
                             and not p["supported_at_95"]]
        if len(group2) > 1:
            summary.append("<li><strong>Entre eux,</strong> %s : aucun écart établi. Ces tâches ne montrent "
                           "aucune raison de payer plus pour l'un que pour l'autre.</li>" % ", ".join(name(m) for m in group2))
            priced2 = [m for m in group2 if m in prices]
            if len(priced2) > 1:
                cheap2 = min(priced2, key=lambda m: prices[m][1])
                dear2 = max(priced2, key=lambda m: prices[m][1])
                if cheap2 != dear2:
                    summary.append("<li><strong>Le point qui compte pour le budget :</strong> dans ce groupe, %s coûte "
                                   "environ %s fois moins cher en jetons de sortie (prix catalogue) que %s, sans être "
                                   "démontré moins bon sur ces tâches. Ce n'est pas la preuve qu'il est aussi bon : "
                                   "c'est ce que le test sur <em>vos</em> tâches doit trancher.</li>"
                                   % (name(cheap2), fr(prices[dear2][1] / prices[cheap2][1], 0), name(dear2)))
        if best in prices and second in prices:
            summary.append("<li><strong>La vraie question devient :</strong> les %s points d'avance établis de %s "
                           "valent-ils un prix de sortie %s fois plus élevé que celui de %s ?</li>"
                           % (fr(100 * (a["scores"][best] - a["scores"][second])), name(best),
                              fr(prices[best][1] / prices[second][1], 1), name(second)))
    if cheapest and cheapest != best and best in prices:
        ratio = prices[best][1] / prices[cheapest][1]
        summary.append("<li><strong>Le point qui compte pour le budget :</strong> %s, dans le groupe de tête, coûte "
                       "environ %s fois moins cher en jetons de sortie (prix catalogue) que %s, sans être démontré moins bon "
                       "sur ces tâches. « Pas démontré moins bon » ne veut pas dire « aussi bon » : c'est ce que le test "
                       "sur <em>vos</em> tâches doit trancher.</li>" % (name(cheapest), fr(ratio, 0), name(best)))
    summary.append("<li><strong>%d tâches sur %d</strong> donnent le même résultat aux %d modèles (%d réussies par tous, "
                   "%d ratées par tous) : elles coûtent à chaque évaluation sans jamais départager.</li>"
                   % (a["same_result"], n, len(models), a["all_right"], a["all_wrong"]))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root{--ink:#16181d;--soft:#4a4f5a;--page:#fff;--panel:#f4f5f7;--line:#d9dce2;--ok:#17784a;--no:#9a5a00;--link:#1a4fb4}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#e6e8ec;--soft:#a0a6b2;--page:#14161a;--panel:#1c1f25;--line:#333844;--ok:#6bd39e;--no:#f0b65a;--link:#7fa6f0}}
:root[data-theme="dark"]{--ink:#e6e8ec;--soft:#a0a6b2;--page:#14161a;--panel:#1c1f25;--line:#333844;--ok:#6bd39e;--no:#f0b65a;--link:#7fa6f0}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:52rem;margin:0 auto;padding:2rem 16px 4rem}
h1{font-size:1.7rem;line-height:1.2;margin:0 0 .5rem}h2{font-size:1.15rem;margin:2.2rem 0 .6rem}
.soft{color:var(--soft)}.small{font-size:.88rem}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:1rem 1.2rem}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%%;font-size:.93rem}
th,td{border-bottom:1px solid var(--line);padding:.45rem .5rem;text-align:left;vertical-align:top}
th{font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.ok{color:var(--ok);font-weight:600}.no{color:var(--no);font-weight:600}a{color:var(--link)}
</style></head><body><main class="wrap">
<p class="soft small">Item Audit — rapport « choix de modèle vérifié » — exemple sur données publiques — %(stamp)s</p>
<h1>%(title)s</h1>
<p class="soft">%(source)s</p>
<div class="panel"><h2 style="margin-top:0">En bref</h2><ul>%(summary)s</ul></div>
<h2>1. Les scores, avec leur incertitude</h2>
<div class="scroll"><table><tr><th>Modèle</th><th class=num>Score</th><th class=num>Intervalle à 95 %%</th><th class=num>Prix catalogue (entrée / sortie, $ par million de jetons)</th></tr>%(rows)s</table></div>
<p class="small soft">Un score seul ne dit rien de l'écart avec un autre modèle : la comparaison se fait par paires, ci-dessous.</p>
<h2>2. Chaque paire, sur les mêmes %(n)d tâches</h2>
<div class="scroll"><table><tr><th>Modèle A</th><th>Modèle B</th><th class=num>Écart A − B (points)</th><th class=num>Intervalle à 95 %%</th><th class=num>p (McNemar exact)</th><th class=num>Seul A réussit / seul B réussit</th><th>Lecture</th></tr>%(prow)s</table></div>
<p class="small soft">Seules les tâches où les deux modèles divergent disent lequel est meilleur ; c'est ce que compte le test apparié. Aucune correction pour comparaisons multiples : elle ne ferait qu'élargir le groupe de tête.</p>
<h2>3. Comment lire ce rapport</h2>
<ul><li><strong>« Écart établi »</strong> : la différence dépasse ce que le hasard des tâches explique, au seuil de 95 %%.</li>
<li><strong>« Écart non établi »</strong> : pas démontré avec ces tâches. Cela ne veut pas dire que les deux modèles se valent ; il faudrait plus de tâches, ou vos propres tâches, pour trancher.</li>
<li><strong>Sur vos tâches</strong>, le classement peut changer : c'est l'objet du service — les mêmes calculs, sur votre travail réel, avec un panel séparé d'au moins 30 modèles pour vérifier que vos tâches mesurent bien.</li></ul>
<h2>4. Limites</h2>
<ul class="small"><li>Données publiques, réglages de chaque modèle tels qu'évalués par la source ; un fournisseur peut annoncer d'autres chiffres avec d'autres réglages.</li>
<li>Les prix sont des prix catalogue par jeton ; le coût réel d'une tâche dépend du nombre de jetons qu'elle consomme, qui varie d'un modèle à l'autre.</li>
<li>Un exemple public n'est pas un audit de vos usages.</li></ul>
<p class="small soft">Méthode et code publics : <a href="https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026">dépôt GitHub</a> · Contact : rubens.alphe0@gmail.com</p>
</main></body></html>
""" % {"title": esc(title), "source": esc(source), "summary": "".join(summary), "rows": "".join(rows),
       "prow": "".join(prow), "n": n, "stamp": stamp}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--models", required=True, help="comma-separated trial names, at most six")
    parser.add_argument("--labels", type=Path, help="JSON {trial: display name}")
    parser.add_argument("--prices", type=Path, help="JSON {trial: [input $/M tokens, output $/M tokens]}")
    parser.add_argument("--title", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not 2 <= len(models) <= 6:
        raise SystemExit("give between two and six models")
    by = load_table(args.table)
    missing = [m for m in models if m not in by]
    if missing:
        raise SystemExit("not in the table: %s" % ", ".join(missing))
    labels = json.loads(args.labels.read_text(encoding="utf-8")) if args.labels else {}
    prices = json.loads(args.prices.read_text(encoding="utf-8")) if args.prices else {}
    result = analyse(by, models)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(args.title, args.source, models, labels, prices, result), encoding="utf-8")
    print(json.dumps({"items": len(result["items"]), "order": result["order"], "leading": result["leading"],
                      "same_result": result["same_result"]}, indent=1))


if __name__ == "__main__":
    main()
