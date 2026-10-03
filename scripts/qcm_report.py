#!/usr/bin/env python3
"""The QCM report a teacher or trainer receives: which questions to fix, and the grades with them fixed.

Input: a CSV of a class's answers in the format of the free web checker (a
header Nom;Q1;Q2..., a row CORRIGÉ with the keyed letters, one row per
student), or 0/1 scores without a key row. Output: a self-contained French
HTML report with:

- each question's success rate and discrimination (corrected point-biserial),
  the answer distribution in the strongest and weakest thirds, and a verdict;
- suspect keys, where the strongest students favour another letter;
- the test's reliability (KR-20), and what it becomes without the defective
  questions;
- every student's grade out of 20 as marked, re-marked with the suspect keys
  changed to the letter the strongest students chose, and without the
  defective questions — so the teacher sees what is at stake before deciding.

Several files (one per session of the same quiz, oldest first) produce the
"pack formateur" report instead: each question followed over time, with
alerts when it degrades.

  python scripts/qcm_report.py --out rapport.html classe.csv
  python scripts/qcm_report.py --out suivi.html session1.csv session2.csv session3.csv
"""

from __future__ import annotations

import argparse
import html
import math
import unicodedata
from pathlib import Path

KEY_NAMES = {"CORRIGE", "CLE", "KEY", "REPONSES"}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def parse(text: str) -> dict:
    lines = [l for l in text.replace("\r", "").split("\n") if l.strip()]
    if len(lines) < 3:
        raise SystemExit("need a header and at least two rows")
    sep = max([";", "\t", ","], key=lambda s: lines[0].count(s))
    rows = [[c.strip() for c in l.split(sep)] for l in lines]
    head = rows[0][1:]
    key, people = None, []
    for r in rows[1:]:
        if strip_accents(r[0]).upper() in KEY_NAMES:
            key = [c.upper() for c in r[1:]]
        else:
            people.append(r)
    names = [r[0] for r in people]
    if key is None:
        scored = [[1 if (r[j + 1] if j + 1 < len(r) else "") == "1" else 0 for j in range(len(head))] for r in people]
        answers = None
    else:
        answers = [[(r[j + 1] if j + 1 < len(r) else "").upper() for j in range(len(head))] for r in people]
        scored = [[1 if a and a == key[j] else 0 for j, a in enumerate(row)] for row in answers]
    if len(scored) < 5:
        raise SystemExit("need at least five respondents")
    return {"head": head, "key": key, "names": names, "answers": answers, "scored": scored}


def corr(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


def kr20(scored: list[list[int]], keep: list[int]) -> float | None:
    k = len(keep)
    if k < 2:
        return None
    n = len(scored)
    totals = [sum(r[j] for j in keep) for r in scored]
    mean = sum(totals) / n
    var = sum((t - mean) ** 2 for t in totals) / n
    pq = sum((p := sum(r[j] for r in scored) / n) * (1 - p) for j in keep)
    return (k / (k - 1)) * (1 - pq / var) if var else None


def analyse(d: dict) -> dict:
    n, k = len(d["scored"]), len(d["head"])
    totals = [sum(r) for r in d["scored"]]
    order = sorted(range(n), key=lambda i: -totals[i])
    third = max(3, round(n / 3))
    top, bottom = order[:third], order[-third:]
    items = []
    for j, q in enumerate(d["head"]):
        col = [r[j] for r in d["scored"]]
        rest = [totals[i] - col[i] for i in range(n)]
        p, r = sum(col) / n, corr(col, rest)
        dist = None
        suggestion = None
        if d["answers"]:
            def share(group):
                counts = {}
                for i in group:
                    a = d["answers"][i][j] or "—"
                    counts[a] = counts.get(a, 0) + 1
                return counts
            dist = {"top": share(top), "bottom": share(bottom)}
            keyed = d["key"][j]
            best = max(dist["top"], key=lambda a: dist["top"][a])
            if best not in (keyed, "—") and dist["top"][best] / len(top) > 0.5 and dist["top"][best] - dist["top"].get(keyed, 0) >= 2:
                suggestion = best
        if p > 0.9:
            verdict, level = "Très facile", 1
        elif r is not None and r < 0 and suggestion:
            verdict, level = "Corrigé suspect", 3
        elif r is not None and r < 0:
            verdict, level = "À relire", 2
        elif r is None or r < 0.15:
            verdict, level = "Ne départage pas", 2
        elif p < 0.2:
            verdict, level = "Très difficile", 1
        else:
            verdict, level = "Bonne question", 0
        items.append({"j": j, "q": q, "p": p, "r": r, "verdict": verdict, "level": level, "dist": dist,
                      "suggestion": suggestion})
    all_items = list(range(k))
    defective = [it["j"] for it in items if it["level"] >= 2]
    kept = [j for j in all_items if j not in defective]
    rekey = {it["j"]: it["suggestion"] for it in items if it["level"] == 3 and it["suggestion"]}
    students = []
    for i, name in enumerate(d["names"]):
        as_marked = 20 * totals[i] / k
        if d["answers"] and rekey:
            fixed = sum(1 if (j in rekey and d["answers"][i][j] == rekey[j]) or (j not in rekey and d["scored"][i][j]) else 0
                        for j in all_items)
            rekeyed = 20 * fixed / k
        else:
            rekeyed = None
        without = 20 * sum(d["scored"][i][j] for j in kept) / len(kept) if kept else None
        students.append({"name": name, "marked": as_marked, "rekeyed": rekeyed, "without": without})
    return {"n": n, "k": k, "items": items, "kr20": kr20(d["scored"], all_items),
            "kr20_kept": kr20(d["scored"], kept), "kept": len(kept), "rekey": rekey, "students": students}


def fr(x: float | None, d: int = 2) -> str:
    return "—" if x is None else (("%." + str(d) + "f") % x).replace(".", ",")


STYLE = """
:root{--ink:#1b2430;--soft:#5b6676;--page:#fff;--panel:#f6f7f9;--line:#d8dde5;--pen:#c21d2e;--amber:#8a5a00;--ok:#1d6b45}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#e4e8ee;--soft:#9aa5b4;--page:#12161c;--panel:#1a2028;--line:#2c3542;--pen:#ff7a86;--amber:#f2c063;--ok:#74d3a0}}
:root[data-theme="dark"]{--ink:#e4e8ee;--soft:#9aa5b4;--page:#12161c;--panel:#1a2028;--line:#2c3542;--pen:#ff7a86;--amber:#f2c063;--ok:#74d3a0}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:54rem;margin:0 auto;padding:2rem 16px 4rem}h1{font-size:1.7rem;margin:0 0 .4rem}h2{font-size:1.15rem;margin:2rem 0 .6rem}
.soft{color:var(--soft)}.small{font-size:.88rem}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:1rem 1.2rem}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{border-bottom:1px solid var(--line);padding:.4rem .5rem;text-align:left;vertical-align:top}
th{font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.l3{color:var(--pen);font-weight:700}.l2{color:var(--amber);font-weight:700}.l1{color:var(--soft);font-weight:600}.l0{color:var(--ok);font-weight:600}
"""


def page(title: str, body: str) -> str:
    return ("<!DOCTYPE html><html lang=fr><head><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><main class=wrap>%s"
            "<p class='small soft'>Item Audit. Méthode : analyse classique des items "
            "(taux de réussite, corrélation point-bisériale corrigée, KR-20). Un signal dit quoi relire ; il ne prouve pas "
            "l'erreur. Ce rapport n'est pas une certification de votre examen.</p></main></body></html>"
            % (html.escape(title), STYLE, body))


def single_report(name: str, d: dict, a: dict) -> str:
    e = html.escape
    suspects = [it for it in a["items"] if it["level"] == 3]
    weak = [it for it in a["items"] if it["level"] == 2]
    summary = ["<li><strong>%d répondants, %d questions.</strong> Fiabilité du test (KR-20) : %s "
               "(une valeur de 0,70 ou plus est souhaitable pour un examen qui compte).</li>" % (a["n"], a["k"], fr(a["kr20"]))]
    if suspects:
        summary.append("<li><strong>Corrigé suspect :</strong> %s. Les élèves les plus forts y choisissent majoritairement une "
                       "autre lettre que celle du corrigé.</li>" % ", ".join(
                           "%s (corrigé %s, les plus forts répondent %s)" % (e(it["q"]), d["key"][it["j"]], it["suggestion"]) for it in suspects))
    if weak:
        summary.append("<li><strong>À relire :</strong> %s. Elles ne départagent pas les élèves, ou les forts y réussissent "
                       "moins bien.</li>" % ", ".join(e(it["q"]) for it in weak))
    if a["kept"] < a["k"]:
        summary.append("<li><strong>Sans ces questions</strong>, le test garde %d questions et sa fiabilité passe à %s.</li>"
                       % (a["kept"], fr(a["kr20_kept"])))
    if not suspects and not weak:
        summary.append("<li>Aucune question défectueuse n'est signalée.</li>")
    if a["n"] < 30:
        summary.append("<li class=small>Avec moins de 30 répondants, les signaux sont moins sûrs : à 20 répondants, environ "
                       "1 question saine sur 7 reçoit une discrimination négative par hasard. Relisez avant de conclure.</li>")
    rows = []
    for it in sorted(a["items"], key=lambda x: (-x["level"], x["r"] if x["r"] is not None else -9)):
        dist = ""
        if it["dist"]:
            def fmt(c):
                total = sum(c.values())
                return " · ".join("%s %d %%" % (k, round(100 * v / total)) for k, v in sorted(c.items()))
            dist = "Plus forts : %s<br>Plus faibles : %s" % (fmt(it["dist"]["top"]), fmt(it["dist"]["bottom"]))
        rows.append("<tr><td><strong>%s</strong>%s</td><td class=num>%d %%</td><td class=num>%s</td><td class=l%d>%s</td><td class=small>%s</td></tr>"
                    % (e(it["q"]), " (corrigé %s)" % d["key"][it["j"]] if d["key"] else "", round(100 * it["p"]), fr(it["r"]),
                       it["level"], it["verdict"], dist))
    srows = []
    for s in a["students"]:
        srows.append("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
                     % (e(s["name"]), fr(s["marked"], 1), fr(s["rekeyed"], 1), fr(s["without"], 1)))
    body = ("<p class='soft small'>Rapport d'analyse de QCM — %s</p><h1>Votre QCM, question par question</h1>"
            "<div class=panel><h2 style='margin-top:0'>En bref</h2><ul>%s</ul></div>"
            "<h2>1. Chaque question</h2><div class=scroll><table><tr><th>Question</th><th class=num>Réussite</th>"
            "<th class=num>Discrimination</th><th>Diagnostic</th><th>Réponses des plus forts et des plus faibles (tiers)</th></tr>%s</table></div>"
            "<p class='small soft'>Discrimination : corrélation entre la réussite à la question et le reste du test. Au-dessus de "
            "0,15, la question distingue bien ; négative, les plus forts y réussissent moins bien que les autres.</p>"
            "<h2>2. Les notes sur 20, selon votre décision</h2><div class=scroll><table><tr><th>Élève</th><th class=num>Note actuelle</th>"
            "<th class=num>Si le corrigé suspect est changé</th><th class=num>Sans les questions défectueuses</th></tr>%s</table></div>"
            "<p class='small soft'>La décision vous appartient : relisez chaque question signalée avant de changer un corrigé.</p>"
            % (e(name), "".join(summary), "".join(rows), "".join(srows)))
    return page("Rapport QCM — %s" % name, body)


def history_report(names: list[str], analyses: list[dict]) -> str:
    e = html.escape
    labels = []
    for a in analyses:
        for it in a["items"]:
            if it["q"] not in labels:
                labels.append(it["q"])
    head = "".join("<th class=num>%s<br><span class=soft>réussite · discr.</span></th>" % e(n) for n in names)
    rows, alerts = [], []
    for q in labels:
        cells, series = [], []
        for a in analyses:
            it = next((x for x in a["items"] if x["q"] == q), None)
            series.append(it)
            cells.append("<td class=num>—</td>" if it is None else
                         "<td class='num l%d'>%d %% · %s</td>" % (it["level"], round(100 * it["p"]), fr(it["r"])))
        present = [it for it in series if it is not None]
        alert = ""
        if len(present) >= 2:
            last, prev = present[-1], present[-2]
            if last["level"] == 3:
                alert = "Corrigé suspect à la dernière session"
            elif last["p"] - prev["p"] > 0.25:
                alert = "Devenue nettement plus facile : question connue des élèves ?"
            elif prev["p"] - last["p"] > 0.25:
                alert = "Devenue nettement plus difficile : cours modifié ?"
            elif last["r"] is not None and prev["r"] is not None and prev["r"] - last["r"] > 0.25:
                alert = "Ne départage plus aussi bien (discrimination en baisse)"
        elif present and present[-1]["level"] == 3:
            alert = "Corrigé suspect"
        if alert:
            alerts.append("<li><strong>%s</strong> : %s</li>" % (e(q), alert))
        rows.append("<tr><td><strong>%s</strong></td>%s<td class=small>%s</td></tr>" % (e(q), "".join(cells), alert))
    body = ("<p class='soft small'>Pack formateur — suivi de %d sessions</p><h1>Vos questions, session après session</h1>"
            "<div class=panel><h2 style='margin-top:0'>Alertes</h2><ul>%s</ul></div>"
            "<h2>Le suivi</h2><div class=scroll><table><tr><th>Question</th>%s<th>Alerte</th></tr>%s</table></div>"
            "<h2>Fiabilité de chaque session</h2><ul>%s</ul>"
            % (len(names), "".join(alerts) or "<li>Aucune alerte.</li>", head, "".join(rows),
               "".join("<li>%s : KR-20 %s, %d répondants</li>" % (e(n), fr(a["kr20"]), a["n"]) for n, a in zip(names, analyses))))
    return page("Suivi QCM — pack formateur", body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="one CSV per session, oldest first")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    parsed = [parse(f.read_text(encoding="utf-8-sig")) for f in args.files]
    analyses = [analyse(d) for d in parsed]
    if len(args.files) == 1:
        out = single_report(args.files[0].stem, parsed[0], analyses[0])
    else:
        out = history_report([f.stem for f in args.files], analyses)
    args.out.write_text(out, encoding="utf-8")
    print("written %s" % args.out)


if __name__ == "__main__":
    main()
