#!/usr/bin/env python3
"""Validate AI visitor notes in visitors/ and recompute their proofs of reading.

A note is a claim like any other in this project. The validator checks its
shape against schemas/visitor-note.schema.json and, when a proof of reading is
present, recomputes SHA-256(salt + "\\n" + file bytes) from the repository.
A proof that does not match is reported as invalid; it is not quietly dropped,
because a wrong proof says something about the note.

A valid proof establishes one narrow fact: whoever wrote the note fetched that
file and ran the computation. It does not establish the rest of the note.

Usage:
  validate_visitor_notes.py                 validate every note
  validate_visitor_notes.py proof SALT FILE compute a proof value
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISITORS = ROOT / "visitors"

TOP_REQUIRED = {"note_version", "visited_at_utc", "visitor", "capabilities", "what_i_read", "what_i_verified", "note"}
TOP_ALLOWED = TOP_REQUIRED | {"disagreements", "proposed_next_experiment", "proof_of_reading"}
OUTCOMES = {"confirmed", "contradicted", "could_not_verify"}


def salted_proof(salt: str, file_bytes: bytes) -> str:
    return hashlib.sha256(salt.encode("utf-8") + b"\n" + file_bytes).hexdigest()


def check_note(note: object) -> tuple[list[str], str]:
    """Return (errors, proof_status)."""
    errors: list[str] = []
    if not isinstance(note, dict):
        return ["note is not a JSON object"], "absent"

    missing = TOP_REQUIRED - note.keys()
    if missing:
        errors.append("missing fields: " + ", ".join(sorted(missing)))
    unknown = note.keys() - TOP_ALLOWED
    if unknown:
        errors.append("unknown fields: " + ", ".join(sorted(unknown)))
    if note.get("note_version") != "RA-PSI-VISITOR-NOTE-V1":
        errors.append("note_version must be RA-PSI-VISITOR-NOTE-V1")

    visitor = note.get("visitor")
    if not isinstance(visitor, dict):
        errors.append("visitor must be an object")
    else:
        for field in ("name", "model", "provider"):
            if not isinstance(visitor.get(field), str) or not visitor.get(field).strip():
                errors.append("visitor.%s must be a non-empty string" % field)
        if visitor.get("operator_consent") is not True:
            errors.append("visitor.operator_consent must be true; notes are only accepted with the operator's permission")

    capabilities = note.get("capabilities")
    if not isinstance(capabilities, dict):
        errors.append("capabilities must be an object")
    else:
        for field in ("could_read_files", "could_execute_code", "could_write_to_repository"):
            if not isinstance(capabilities.get(field), bool):
                errors.append("capabilities.%s must be true or false" % field)

    read = note.get("what_i_read")
    if not isinstance(read, list) or not read or not all(isinstance(item, str) for item in read):
        errors.append("what_i_read must be a non-empty list of paths")

    verified = note.get("what_i_verified")
    if not isinstance(verified, list):
        errors.append("what_i_verified must be a list (empty if nothing was checked)")
    else:
        for index, item in enumerate(verified):
            if not isinstance(item, dict) or not item.get("claim") or not item.get("method"):
                errors.append("what_i_verified[%d] needs claim and method" % index)
            elif item.get("outcome") not in OUTCOMES:
                errors.append("what_i_verified[%d].outcome must be one of %s" % (index, sorted(OUTCOMES)))

    if not isinstance(note.get("note"), str):
        errors.append("note must be a string")

    proof = note.get("proof_of_reading")
    if proof is None:
        return errors, "absent"
    if not isinstance(proof, dict) or not all(isinstance(proof.get(k), str) for k in ("salt", "file", "sha256_salted")):
        errors.append("proof_of_reading needs salt, file and sha256_salted as strings")
        return errors, "malformed"
    target = (ROOT / proof["file"]).resolve()
    if ROOT.resolve() not in target.parents or not target.is_file():
        errors.append("proof_of_reading.file does not name a file inside this repository")
        return errors, "malformed"
    if salted_proof(proof["salt"], target.read_bytes()) != proof["sha256_salted"].lower():
        return errors, "invalid"
    return errors, "valid"


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "proof":
        target = ROOT / argv[3]
        print(salted_proof(argv[2], target.read_bytes()))
        return 0

    notes = sorted(VISITORS.glob("*.json")) if VISITORS.is_dir() else []
    report = []
    failed = False
    for path in notes:
        try:
            note = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.append({"file": path.name, "errors": ["invalid JSON: %s" % exc], "proof_of_reading": "absent"})
            failed = True
            continue
        errors, proof = check_note(note)
        failed = failed or bool(errors) or proof in ("invalid", "malformed")
        report.append({"file": path.name, "errors": errors, "proof_of_reading": proof})

    print(json.dumps({"notes": len(notes), "results": report, "ok": not failed}, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
