#!/usr/bin/env python3
"""A private demonstration of the two-step offer for training providers, on synthetic data.

Step 1, before a QCM goes live: an inexpensive model reads each question and
its key and flags the keys that look wrong. The verdicts shown are the real,
stored outputs of DIAGNOSIS-UNSEEN-2026-10 on its new questions, some of
whose keys were deliberately changed; no model is called here.

Step 2, after a first session: the statistical report on learners' answers.
The learners are simulated (they answer according to the true key), so the
demonstration can show what the statistics confirm.

Everything is marked as a demonstration on synthetic data. The figures that
may be quoted to a buyer are those of the published studies, not this demo.

  python scripts/demo_formation.py --out demo-formation.html
"""

from __future__ import annotations

import argparse
import html
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import qcm_report as qr  # noqa: E402

UNSEEN = ROOT / "experiments" / "DIAGNOSIS-UNSEEN-2026-10"
MODULES = [("professional accounting", "Comptabilité"), ("computer security", "Cybersécurité")]
LEARNERS, SEED = 40, 20261004


def load_module(subject: str) -> list[dict]:
    sample = json.loads((UNSEEN / "sample.json").read_text(encoding="utf-8"))
    items = [i for i in sample if i["subject"] == subject]
    for item in items:
        verdict = json.loads((UNSEEN / "diagnosed" / (item["id"] + ".json")).read_text(encoding="utf-8"))
        item["verdict"] = verdict.get("verdict") or "NO_VERDICT"
        item["best_option"] = verdict.get("best_option")
        item["reason"] = verdict.get("reason", "")
    return items


def simulate(items: list[dict], rng: random.Random) -> str:
    """Learners answer according to the true key; the file carries the key as published."""
    lines = ["Nom;" + ";".join("Q%d" % (j + 1) for j in range(len(items))),
             "CORRIGÉ;" + ";".join(i["key"] for i in items)]
    difficulty = [rng.uniform(-1.5, 1.0) for _ in items]
    for s in range(LEARNERS):
        theta = rng.gauss(0, 1.2)
        row = []
        for j, item in enumerate(items):
            p = 0.2 + 0.8 / (1 + math.exp(-2.2 * (theta - difficulty[j])))
            if rng.random() < p:
                row.append(item["original_key"])
            elif item["planted"] and rng.random() < 0.6:
                row.append(item["key"])  # the published wrong key attracts the weaker learners
            else:
                row.append(rng.choice([l for l in "ABCD" if l != item["original_key"]]))
        lines.append("Apprenant %02d;" % (s + 1) + ";".join(row))
    return "\n".join(lines)


VERDICT_FR = {"KEY_OK": "corrigé cohérent", "KEY_WRONG": "corrigé probablement faux",
              "MULTIPLE_CORRECT": "plusieurs réponses défendables", "NO_CORRECT_ANSWER": "aucune réponse juste",
              "UNCLEAR": "énoncé ambigu", "NO_VERDICT": "pas de verdict"}


def section(label: str, items: list[dict], rng: random.Random) -> tuple[str, dict]:
    e = html.escape
    flagged = [i for i in items if i["verdict"] not in ("KEY_OK",)]
    planted = [i for i in items if i["planted"]]
    caught = [i for i in planted if i["verdict"] == "KEY_WRONG"]
    rows = []
    for j, item in enumerate(items):
        if item["verdict"] == "KEY_OK":
            continue
        rows.append("<tr><td>Q%d</td><td class=small>%s</td><td class=num>%s</td><td class=l3>%s%s</td><td class=small>%s</td><td>%s</td></tr>"
                    % (j + 1, e(item["question"][:160]) + ("…" if len(item["question"]) > 160 else ""), e(item["key"]),
                       VERDICT_FR.get(item["verdict"], item["verdict"]),
                       " (proposé : %s)" % e(item["best_option"]) if item["best_option"] else "",
                       e(item["reason"][:220]), "oui" if item["planted"] else "non"))
    data = qr.parse(simulate(items, rng))
    stats = qr.analyse(data)
    suspects = [it for it in stats["items"] if it["level"] == 3]
    planted_ids = {j for j, item in enumerate(items) if item["planted"]}
    confirmed = [it for it in suspects if it["j"] in planted_ids]
    body = ("<h2>Module « %s » — %d questions</h2>"
            "<h3>Étape 1 : avant la mise en ligne (texte des questions seulement)</h3>"
            "<p>L'IA signale <strong>%d question(s)</strong>. Dans cette démonstration, nous savons que <strong>%d</strong> corrigé(s) "
            "avaient été faussés exprès ; l'IA en désigne %d.</p>"
            "<div class=scroll><table><tr><th>Question</th><th>Énoncé (extrait, en anglais)</th><th>Corrigé publié</th>"
            "<th>Avis de l'IA</th><th>Explication de l'IA (extrait)</th><th>Faussé exprès&nbsp;?</th></tr>%s</table></div>"
            "<h3>Étape 2 : après une première session (%d apprenants simulés)</h3>"
            "<p>L'analyse des réponses classe <strong>%d question(s)</strong> en « corrigé suspect »%s.</p>"
            % (e(label), len(items), len(flagged), len(planted), len(caught), "".join(rows) or "<tr><td colspan=6>Aucune question signalée.</td></tr>",
               LEARNERS, len(suspects),
               " : %s, dont %d parmi les corrigés faussés exprès" % (", ".join("Q%d (les plus forts répondent %s)" % (it["j"] + 1, e(it["suggestion"])) for it in suspects), len(confirmed)) if suspects else ""))
    return body, {"questions": len(items), "flagged": len(flagged), "planted": len(planted), "caught": len(caught),
                  "suspects": len(suspects), "confirmed": len(confirmed)}


def page(sections: list[str]) -> str:
    intro = ("<p class='soft small'>DÉMONSTRATION PRIVÉE — données synthétiques — ne pas diffuser comme un résultat client</p>"
             "<h1>Le chef de vos QCM : il refuse avant la mise en ligne, les statistiques confirment après</h1>"
             "<div class=panel><p>Un organisme de formation fictif publie deux modules de QCM. Une partie des questions a été écrite par une IA, "
             "et quelques corrigés ont été faussés exprès pour la démonstration.</p><ul>"
             "<li><strong>Étape 1</strong> : avant toute session, une IA relit chaque question et son corrigé. Les avis affichés sont les "
             "sorties réelles et conservées de notre étude pré-inscrite DIAGNOSIS-UNSEEN-2026-10 ; aucune n'a été retouchée.</li>"
             "<li><strong>La boucle du chef</strong> : les questions refusées repartent en correction chez vous, puis le chef les relit ; la boucle s'arrête quand il n'a plus rien à refuser. Cette démonstration montre le premier passage.</li>"
             "<li><strong>Étape 2</strong> : après une première session, l'analyse statistique des réponses (ici, des apprenants simulés) "
             "confirme ou non les questions à revoir, et recalcule les notes.</li></ul></div>")
    caution = ("<h2>Ce qu'il faut retenir, honnêtement</h2><ul>"
               "<li>Les erreurs de cette démonstration ont été <strong>glissées exprès</strong> : elles sont plus faciles à repérer que de "
               "vraies erreurs. Sur de vraies erreurs relevées par des experts (DIAGNOSIS-REDUX-2026-10), quand l'IA signale un corrigé "
               "faux, elle a raison 43 % du temps, contre 11 % pour le seul signal statistique.</li>"
               "<li>Un signal dit quoi relire en premier ; la décision reste à votre équipe pédagogique.</li>"
               "<li>Les apprenants de l'étape 2 sont simulés. Sur vos sessions réelles, la fiabilité dépend du nombre d'apprenants.</li>"
               "<li>Ce n'est pas une certification de vos QCM.</li></ul>")
    return qr.page("Démonstration — QCM de formation vérifiés", intro + "".join(sections) + caution)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(SEED)
    bodies, summary = [], {}
    for subject, label in MODULES:
        body, stats = section(label, load_module(subject), rng)
        bodies.append(body)
        summary[label] = stats
    args.out.write_text(page(bodies), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
