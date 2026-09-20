#!/usr/bin/env python3
"""Check that a project's published numbers still follow from its own evidence.

`regression_suite.py` does this for this repository and knows four of its result
shapes by heart. That knowledge is the reason it works here and the reason it is
useless anywhere else. This is the portable form, and it works by refusing to
guess: a project **declares** its claims, and the declaration is the product.

A `claims.json` names, for each published number: where it is published, what it
is, what evidence it rests on, and the command that recomputes it. Then:

- a claim with no recompute command is **UNVERIFIABLE** — not wrong, not
  checked, and never silently counted as fine;
- a claim whose evidence has moved since the manifest was written is
  **EVIDENCE_CHANGED**;
- a claim whose recomputation disagrees with what is published is **MISMATCH**.

Exit codes: 0 clean, 1 a mismatch, 2 unverifiable or changed evidence only.
"We did not keep the evidence" must never report as "it checks out" — that
distinction is the whole of this tool, and it is the one this project got wrong
about itself before the suite existed.

Hashing alone would not be enough, and this project has the receipt: its
MEM-007 decision file disagreed with its own stored answers while **every hash
still matched**, because the file was derived, published, and then the answers
were re-read. Only recomputation catches that.

**Recomputation runs a command you declared.** This tool will not execute
anything without `--run`, and the commands come from a file in the project being
audited — which is to say, from whoever controls that file. Read a `claims.json`
before running it with `--run`, exactly as you would read a build script.

  python scripts/audit_claims.py --claims claims.json            # verify, execute nothing
  python scripts/audit_claims.py --claims claims.json --run      # recompute too
  python scripts/audit_claims.py --claims claims.json --write-hashes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

TOLERANCE = 1e-9


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dig(payload: object, pointer: str) -> object:
    """Follow a dotted path into parsed JSON, so a claim can name one number."""
    current = payload
    for step in [part for part in pointer.split(".") if part]:
        if isinstance(current, list):
            current = current[int(step)]
        else:
            current = current[step]
    return current


def differences(recomputed: object, published: object, where: str = "") -> list[str]:
    """Every leaf that moved, named by its path, compared as numbers not strings."""
    if isinstance(published, dict) and isinstance(recomputed, dict):
        out = []
        for name in sorted(set(published) | set(recomputed)):
            out += differences(recomputed.get(name), published.get(name), "%s.%s" % (where, name))
        return out
    if isinstance(published, list) and isinstance(recomputed, list):
        if len(published) != len(recomputed):
            return ["%s: %d values published, %d recomputed" % (where, len(published), len(recomputed))]
        out = []
        for index, (left, right) in enumerate(zip(recomputed, published)):
            out += differences(left, right, "%s[%d]" % (where, index))
        return out
    if isinstance(published, (int, float)) and isinstance(recomputed, (int, float)) \
            and not isinstance(published, bool) and not isinstance(recomputed, bool):
        if abs(float(recomputed) - float(published)) > TOLERANCE:
            return ["%s: published %r, recomputed %r" % (where, published, recomputed)]
        return []
    if recomputed != published:
        return ["%s: published %r, recomputed %r" % (where, published, recomputed)]
    return []


def evidence_state(claim: dict, root: Path) -> tuple[str, list[str]]:
    """Whether the files a claim rests on are present and unchanged."""
    problems = []
    for name, recorded in (claim.get("evidence") or {}).items():
        path = root / name
        if not path.is_file():
            problems.append("missing: %s" % name)
            continue
        if recorded and sha256_file(path) != recorded:
            problems.append("changed since the manifest: %s" % name)
    return ("OK" if not problems else "EVIDENCE_CHANGED"), problems


def recompute(claim: dict, root: Path, timeout: int) -> tuple[object, str | None]:
    command = claim.get("recompute")
    if not command:
        return None, "no recompute command declared"
    try:
        done = subprocess.run(command, cwd=str(root), shell=isinstance(command, str),
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "recompute failed to start: %s" % exc
    # A non-zero exit is not a failure to run. A checker that signals a finding
    # by its exit code — as this project's own regression suite does when a
    # number has moved — is exactly the command most worth auditing, and an
    # earlier version of this function reported it as unverifiable. The output
    # is the evidence; the exit code is a summary of it.
    try:
        payload = json.loads(done.stdout)
    except ValueError:
        detail = (done.stderr or done.stdout or "")[-300:]
        if done.returncode != 0:
            return None, "recompute exited %d without printing JSON: %s" % (done.returncode, detail)
        return None, "recompute did not print JSON: %s" % detail
    pointer = claim.get("recompute_pointer", "")
    try:
        return dig(payload, pointer), None
    except (KeyError, IndexError, ValueError) as exc:
        return None, "recompute output has no %r: %s" % (pointer, exc)


def audit(claims_path: Path, run: bool, timeout: int) -> dict:
    manifest = json.loads(claims_path.read_text(encoding="utf-8"))
    root = (claims_path.parent / manifest.get("root", ".")).resolve()
    rows = []
    for claim in manifest.get("claims", []):
        row = {"id": claim.get("id"), "published_in": claim.get("published_in"),
               "published_value": claim.get("value")}
        state, problems = evidence_state(claim, root)
        row["evidence"] = state
        if problems:
            row["evidence_problems"] = problems
        if not run:
            row["status"] = "NOT_RUN" if claim.get("recompute") else "UNVERIFIABLE"
            row["reason"] = ("recompute was not executed; pass --run" if claim.get("recompute")
                             else "no recompute command is declared for this claim")
        else:
            value, error = recompute(claim, root, timeout)
            if error:
                row["status"] = "UNVERIFIABLE"
                row["reason"] = error
            else:
                moved = differences(value, claim.get("value"), claim.get("id", "value"))
                row["status"] = "REPRODUCED" if not moved else "MISMATCH"
                row["recomputed_value"] = value
                if moved:
                    row["moved"] = moved
        if state == "EVIDENCE_CHANGED" and row["status"] == "REPRODUCED":
            row["status"] = "EVIDENCE_CHANGED"
        rows.append(row)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    if counts.get("MISMATCH"):
        status, code = "MISMATCH", 1
    elif counts.get("UNVERIFIABLE") or counts.get("EVIDENCE_CHANGED"):
        status, code = "UNVERIFIABLE", 2
    elif counts.get("NOT_RUN"):
        status, code = "NOT_RUN", 2
    else:
        status, code = "REPRODUCED", 0
    return {"claims_file": str(claims_path), "root": str(root), "counts": counts,
            "status": status, "exit_code": code, "claims": rows}


def write_hashes(claims_path: Path) -> dict:
    """Record the current hash of every declared evidence file.

    Run once, when the claims are published. It records what the evidence was;
    it cannot tell you whether the evidence was ever right.
    """
    manifest = json.loads(claims_path.read_text(encoding="utf-8"))
    root = (claims_path.parent / manifest.get("root", ".")).resolve()
    written = 0
    for claim in manifest.get("claims", []):
        for name in list((claim.get("evidence") or {})):
            path = root / name
            if path.is_file():
                claim["evidence"][name] = sha256_file(path)
                written += 1
    claims_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"claims_file": str(claims_path), "evidence_files_hashed": written}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--run", action="store_true",
                        help="execute each claim's declared recompute command; read the file first")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--write-hashes", action="store_true",
                        help="record the current hash of every evidence file, once, at publication")
    args = parser.parse_args()

    if args.write_hashes:
        print(json.dumps(write_hashes(args.claims), indent=2, ensure_ascii=False))
        return
    result = audit(args.claims, args.run, args.timeout)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["exit_code"]:
        raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    main()
