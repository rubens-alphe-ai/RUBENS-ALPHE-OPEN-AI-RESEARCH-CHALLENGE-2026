#!/usr/bin/env python3
"""Draft a release-day check for every model Epoch AI has added since a given date.

The barometer: when a new model appears in Epoch AI's public benchmark data
(CC BY 4.0), run `launch_check` on it and write a short draft post, in French
and English, that says which of its leads are established at the size of each
benchmark. Drafts only: nothing is published by this script, and a person
approves each post.

  python scripts/barometer.py --since 2026-09-29 --out-dir drafts/
  python scripts/barometer.py --zip benchmark_data.zip --since 2026-09-29 --out-dir drafts/
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launch_check as lc  # noqa: E402

URL = "https://epoch.ai/data/benchmark_data.zip"
AGENT = "RA-PSI-public-audit/1.0 (psychometric re-analysis of published results)"
REPO = "https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026"
CALCULATOR = "https://claude.ai/artifact/RVYRDkJ2SPUwCnwcHK1Jgv"


def download(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        dest.write_bytes(response.read())
    return dest


def new_models(boards: dict, since: str) -> list[tuple[str, str]]:
    dates: dict[str, str] = {}
    for rows in boards.values():
        for entry in lc.best_entries(rows).values():
            if entry["release_date"]:
                dates[entry["model"]] = max(dates.get(entry["model"], ""), entry["release_date"])
    return sorted(((m, d) for m, d in dates.items() if d > since), key=lambda x: (x[1], x[0]))


def pts(x: float) -> str:
    return ("%+.1f" % x).replace(".", ",")


def draft(model: str, date: str, results: list[dict], snapshot: str) -> str:
    firsts = [r for r in results if r["rank"] == 1]
    alone = [r for r in firsts if r["gap_pts"] > 0]
    level = [r for r in firsts if r["gap_pts"] == 0]
    established = [r for r in alone if r["reading"] == "lead established"]
    behind = [r for r in results if r["rank"] > 1]
    behind_clear = [r for r in behind if r["reading"] == "behind the leader, and the gap is established"]

    def lead_line(lang: str) -> str:
        if not alone:
            return ("- Seul premier sur aucun." if lang == "fr" else "- First alone on none.")
        r = max(alone, key=lambda x: x["gap_pts"])
        lo, hi = r["gap_interval_95_pts"]
        if lang == "fr":
            return ("- **Seul premier sur %d** (%s) : %s points, intervalle à 95 %% de %s à %s, avance %s."
                    % (len(alone), r["benchmark"], pts(r["gap_pts"]), pts(lo), pts(hi),
                       "établie" if r in established else "non établie"))
        return ("- **First alone on %d** (%s): %s points, 95%% interval %s to %s, lead %s."
                % (len(alone), r["benchmark"], pts(r["gap_pts"]).replace(",", "."), pts(lo).replace(",", "."),
                   pts(hi).replace(",", "."), "established" if r in established else "not established"))

    fr = ["## Français", "",
          "%s est apparu dans les données publiques d'Epoch AI (date de sortie : %s). Avec leurs propres barres "
          "d'erreur, au %s, sur %d benchmarks comparables :" % (model, date, snapshot, len(results)), "",
          lead_line("fr"),
          "- **À égalité avec le meilleur autre modèle sur %d.**" % len(level),
          "- **Derrière sur %d**, dont %d avec un écart net." % (len(behind), len(behind_clear)), "",
          "« Non établi » veut dire « pas démontré avec cet échantillon », pas « faux ». Méthode prudente "
          "(comparaison non appariée, erreurs publiées par Epoch). Code et chiffres : %s" % REPO, "",
          "Testez vos propres chiffres : %s" % CALCULATOR]
    en = ["## English", "",
          "%s has appeared in Epoch AI's public data (release date %s). Read with its own error bars, as of %s, "
          "on %d comparable benchmarks:" % (model, date, snapshot, len(results)), "",
          lead_line("en"),
          "- **Level with the best other model on %d.**" % len(level),
          "- **Behind on %d**, %d of them clearly." % (len(behind), len(behind_clear)), "",
          "\"Not established\" means not shown at this sample size, not false. Conservative method (unpaired, "
          "Epoch's published errors). Code and numbers: %s" % REPO, "",
          "Test your own numbers: %s" % CALCULATOR]
    table = ["## Detail", "", "| Benchmark | Score | Rank | Best other | Gap, 95% interval | Reading |", "|---|---|---|---|---|---|"]
    for r in results:
        lo, hi = r["gap_interval_95_pts"]
        table.append("| %s | %.1f | %d / %d | %s %.1f | %+.1f [%+.1f, %+.1f] | %s |"
                     % (r["benchmark"], r["score_pct"], r["rank"], r["models_compared"], r["best_other"],
                        r["best_other_pct"], r["gap_pts"], lo, hi, r["reading"]))
    head = ["# Draft barometer post: %s" % model, "",
            "Draft only. Nothing has been published. the owner approves each publication; run "
            "`check_outbound_claims.py` on the final text.", ""]
    return "\n".join(head + fr + [""] + en + [""] + table) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, help="use this bundle instead of downloading the current one")
    parser.add_argument("--since", required=True, help="release date (YYYY-MM-DD); models released after it are drafted")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(".cache/epoch"))
    args = parser.parse_args()

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = args.zip or download(args.cache / ("benchmark_data_%s.zip" % snapshot))
    boards = lc.boards(zipfile.ZipFile(path))
    written = []
    for model, date in new_models(boards, args.since):
        results = [r for r in (lc.check(n, rows, model) for n, rows in boards.items()) if r]
        if not results:
            continue
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out = args.out_dir / ("BAROMETRE_%s_%s.md" % (date, model))
        out.write_text(draft(model, date, sorted(results, key=lambda r: (r["rank"], -r["gap_pts"])), snapshot),
                       encoding="utf-8")
        written.append({"model": model, "release_date": date, "benchmarks": len(results), "draft": str(out)})
    print(json.dumps({"snapshot": snapshot, "since": args.since, "drafts": written}, indent=1))


if __name__ == "__main__":
    main()
