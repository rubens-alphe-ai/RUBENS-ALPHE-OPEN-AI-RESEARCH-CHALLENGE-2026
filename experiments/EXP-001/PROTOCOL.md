# EXP-001 — Blind Mission Reconstruction

Give a fresh model only:
1. the public challenge manifest URL;
2. the public next-problem URL.

Do not provide the original chat.

Save its raw response, validate against the schema, then score:
- mission reconstruction: 25
- state fidelity: 20
- missing information detection: 15
- next experiment quality: 20
- reproducibility: 20
- any critical fabrication: fail

Target: 90/100 with no critical fabrication.
