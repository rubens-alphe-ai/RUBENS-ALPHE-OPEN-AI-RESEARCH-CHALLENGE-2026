#!/usr/bin/env python3
"""The establishment dashboard: every QCM of a school, by subject and class, in one page.

Input: a folder of exported answer files named `Matière__Classe__AAAA-MM-JJ.csv`
(the format of the free web checker). Output, in the target folder:

- `index.html`: the dashboard for the head of school — exams analysed,
  suspect keys found, questions to review, reliability by subject, and the
  exams that need attention first;
- one detailed report per exam (`qcm_report.py`), linked from the dashboard.

  python scripts/qcm_establishment.py --in exports/ --out tableau-de-bord/ --name "Lycée Exemple"
"""

from __future__ import annotations

import argparse
import html
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import qcm_report as qr  # noqa: E402


def describe(path: Path) -> dict:
    parts = path.stem.split("__")
    if len(parts) != 3:
        raise SystemExit("name files Matière__Classe__AAAA-MM-JJ.csv (got %s)" % path.name)
    return {"subject": parts[0].replace("_", " "), "class": parts[1].replace("_", " "), "date": parts[2]}


def build(src: Path, out: Path, name: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    exams = []
    for path in sorted(src.glob("*.csv")):
        meta = describe(path)
        data = qr.parse(path.read_text(encoding="utf-8-sig"))
        result = qr.analyse(data)
        report = "rapport-%s.html" % qr.strip_accents(path.stem).replace(" ", "_")
        (out / report).write_text(qr.single_report("%s — %s — %s" % (meta["subject"], meta["class"], meta["date"]), data, result),
                                  encoding="utf-8")
        exams.append({**meta, "report": report, "n": result["n"], "k": result["k"], "kr20": result["kr20"],
                      "suspect": sum(1 for it in result["items"] if it["level"] == 3),
                      "review": sum(1 for it in result["items"] if it["level"] == 2)})
    if not exams:
        raise SystemExit("no CSV files in %s" % src)
    (out / "index.html").write_text(dashboard(name, exams), encoding="utf-8")
    return {"exams": len(exams), "suspect": sum(e["suspect"] for e in exams)}


def dashboard(name: str, exams: list[dict]) -> str:
    e = html.escape
    total_suspect = sum(x["suspect"] for x in exams)
    total_review = sum(x["review"] for x in exams)
    students = sum(x["n"] for x in exams)
    by_subject = defaultdict(list)
    for x in exams:
        by_subject[x["subject"]].append(x)
    urgent = sorted((x for x in exams if x["suspect"]), key=lambda x: (-x["suspect"], x["date"]))
    tiles = "".join("<div class=panel style='flex:1 1 150px'><div style='font-size:1.6rem;font-weight:700'>%s</div><div class=soft>%s</div></div>" % t
                    for t in [(len(exams), "examens analysés"), (students, "copies"), (total_suspect, "corrigés suspects"),
                              (total_review, "questions à relire")])
    urgent_rows = "".join("<li><a href='%s'>%s — %s — %s</a> : %d corrigé(s) suspect(s)</li>"
                          % (x["report"], e(x["subject"]), e(x["class"]), e(x["date"]), x["suspect"]) for x in urgent) or \
        "<li>Aucun corrigé suspect.</li>"
    subject_rows = []
    for subject, xs in sorted(by_subject.items()):
        rel = [x["kr20"] for x in xs if x["kr20"] is not None]
        subject_rows.append("<tr><td><strong>%s</strong></td><td class=num>%d</td><td class=num>%s</td><td class=num>%d</td><td class=num>%d</td></tr>"
                            % (e(subject), len(xs), qr.fr(sum(rel) / len(rel)) if rel else "—",
                               sum(x["suspect"] for x in xs), sum(x["review"] for x in xs)))
    exam_rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td class=num>%d</td><td class=num>%s</td><td class='num%s'>%d</td><td class=num>%d</td><td><a href='%s'>rapport</a></td></tr>"
                        % (e(x["subject"]), e(x["class"]), e(x["date"]), x["n"], qr.fr(x["kr20"]),
                           " l3" if x["suspect"] else "", x["suspect"], x["review"], x["report"])
                        for x in sorted(exams, key=lambda x: (x["subject"], x["class"], x["date"])))
    body = ("<p class='soft small'>Tableau de bord établissement</p><h1>%s : la qualité de vos évaluations</h1>"
            "<div style='display:flex;flex-wrap:wrap;gap:12px'>%s</div>"
            "<h2>À traiter en premier</h2><ul>%s</ul>"
            "<h2>Par matière</h2><div class=scroll><table><tr><th>Matière</th><th class=num>Examens</th><th class=num>Fiabilité moyenne (KR-20)</th>"
            "<th class=num>Corrigés suspects</th><th class=num>Questions à relire</th></tr>%s</table></div>"
            "<h2>Tous les examens</h2><div class=scroll><table><tr><th>Matière</th><th>Classe</th><th>Date</th><th class=num>Copies</th>"
            "<th class=num>KR-20</th><th class=num>Suspects</th><th class=num>À relire</th><th></th></tr>%s</table></div>"
            "<p class='small soft'>Une fiabilité de 0,70 ou plus est souhaitable pour un examen qui compte. Avec moins de 30 copies, "
            "les signaux sont moins sûrs : chaque rapport l'indique.</p>"
            % (e(name), tiles, urgent_rows, "".join(subject_rows), exam_rows))
    return qr.page("Tableau de bord — %s" % name, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="src", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", required=True, help="name of the establishment")
    args = parser.parse_args()
    print(build(args.src, args.out, args.name))


if __name__ == "__main__":
    main()
