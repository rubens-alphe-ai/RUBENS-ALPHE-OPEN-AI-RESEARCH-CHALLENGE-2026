#!/usr/bin/env python3
"""Assemble the paste-ready evaluator prompt from an experiment's blind packets.

The prompt is written for a chat model with no tools and no repository access:
it carries its own instruction, the experiment's rubric, every blinded answer
with its hash, and the exact JSON shape to return. It names no condition, no
state file and no hypothesis beyond "two conditions are present".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HEADER = """# Independent evaluation request

You are acting ONLY as an independent evaluator. You did not produce these
answers and you must not rewrite or improve them.

{count} answers are supplied below. Each one was produced by a fresh model
session that received a project description and a fixed prompt, and was asked
to reconstruct the project's mission and state and propose a next experiment.

The answers are BLINDED and SHUFFLED. Two experimental conditions are present.
You are not told which answer belongs to which condition, and you must not try
to guess, infer or mention it. Score each answer on its own merits.

Score every answer against the rubric below, out of 100.

"""

OUTPUT = """

## Required output

Return ONE JSON object and nothing else. No prose before or after.

```json
{{
  "evaluator_id": "<a short stable id you choose>",
  "model": "<the exact model name you are>",
  "provider": "<e.g. OpenAI, Google>",
  "cards": [
    {{
      "blind_id": "BLIND-01",
      "scores": {{
        "mission_reconstruction": 0,
        "current_state_fidelity": 0,
        "failure_recovery": 0,
        "next_action_quality": 0,
        "missing_information_detection": 0,
        "reproducibility": 0,
        "total": 0
      }},
      "critical_fabrications": [
        {{"fabrication_id": "F1", "description": "<what was invented>", "evidence": "<short quote>"}}
      ],
      "notes": "<one or two sentences>"
    }}
  ]
}}
```

Rules:
- one card per blind id, {count} cards total, from BLIND-01 to BLIND-{last};
- `total` must equal the sum of the six component scores;
- component scores must respect the maxima in the rubric;
- `critical_fabrications` is an empty array when you find none. Do not invent
  fabrications to appear rigorous, and do not omit real ones to appear generous;
- never state or speculate about which condition an answer came from.

---
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()

    experiment = ROOT / "experiments" / args.experiment
    packets = experiment / "results" / "blind_packets"
    manifest = json.loads((packets / "packet-manifest.json").read_text(encoding="utf-8"))
    rubric = (experiment / "PCRB1_SCORING.md").read_text(encoding="utf-8")
    entries = manifest["packets"]
    count = len(entries)

    parts = [HEADER.format(count=count), rubric, OUTPUT.format(count=count, last="%02d" % count)]
    for entry in entries:
        text = (packets / ("%s.txt" % entry["blind_id"])).read_text(encoding="utf-8").strip()
        parts.append(
            "\n## %s\n\nSHA-256: `%s`\n\n```text\n%s\n```\n"
            % (entry["blind_id"], entry["output_sha256"], text)
        )

    target = packets / "EVALUATOR_PROMPT.md"
    target.write_text("".join(parts), encoding="utf-8")
    print(json.dumps({"written": str(target.relative_to(ROOT)), "answers": count, "bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
