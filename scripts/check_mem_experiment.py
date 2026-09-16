"""Check readiness of PROP-EXP-MEM-001 without scoring model answers.

The six raw trial files must be collected from fresh, blinded model sessions.
This checker deliberately does not infer semantic scores or accept a memory
architecture; those decisions require the fixed PCRB-1 rubric and an
independent review.
"""

from __future__ import annotations

import json
from pathlib import Path


TRIALS = [
    *(f"baseline_trial_{n:02d}.txt" for n in range(1, 4)),
    *(f"structured_trial_{n:02d}.txt" for n in range(1, 4)),
]


def inspect(results_dir: Path) -> dict[str, object]:
    trials: list[dict[str, object]] = []
    missing: list[str] = []

    for filename in TRIALS:
        path = results_dir / filename
        present = path.is_file()
        nonempty = present and path.stat().st_size > 0
        if not nonempty:
            missing.append(filename)
        trials.append(
            {
                "file": filename,
                "present": present,
                "nonempty": nonempty,
                "bytes": path.stat().st_size if present else 0,
            }
        )

    score_file = results_dir / "scores.json"
    score_file_present = score_file.is_file() and score_file.stat().st_size > 0

    return {
        "experiment_id": "PROP-EXP-MEM-001",
        "ready_for_independent_scoring": not missing,
        "trial_count": len(TRIALS),
        "complete_trial_count": len(TRIALS) - len(missing),
        "missing_files": missing,
        "score_file_present": score_file_present,
        "trials": trials,
        "acceptance_rule": {
            "structured_mean_at_least_baseline_mean_plus": 10,
            "critical_fabrications_must_not_increase": True,
            "canonical_state_change_allowed_before_acceptance": False,
        },
        "note": "Presence is checked automatically; semantic scoring remains independent.",
    }


def main() -> None:
    results_dir = Path(__file__).resolve().parent.parent / "experiments" / "PROP-EXP-MEM-001" / "results"
    print(json.dumps(inspect(results_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
