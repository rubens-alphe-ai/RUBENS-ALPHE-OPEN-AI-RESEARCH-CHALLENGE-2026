#!/usr/bin/env python3
"""Regenerate the public SHA-256 manifest for the project tree."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS.json"
SKIP_DIRS = {".git", "__pycache__", "bridge_state"}
SKIP_NAMES = {"config.local.json", "client_secret.json", "credentials.json", "gmail-token.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_files() -> list[Path]:
    """Files the manifest may certify: git-tracked ones when inside a repository.

    Walking the disk would also hash ignored runtime files -- agent reports,
    ledgers, local caches -- and publish hashes for files that are not part of
    the repository at all. Outside a repository, fall back to the disk walk.
    """
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", "."],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout.decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError):
        return sorted(ROOT.rglob("*"))
    return sorted(ROOT / item for item in listed if item)


def main() -> None:
    entries = {}
    for path in candidate_files():
        if (
            not path.is_file()
            or path == MANIFEST
            or any(part in SKIP_DIRS for part in path.parts)
            or path.name in SKIP_NAMES
            or path.name.endswith(".private.json")
        ):
            continue
        relative = path.relative_to(ROOT).as_posix()
        entries[relative] = sha256(path)
    MANIFEST.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "file_count": len(entries)}, indent=2))


if __name__ == "__main__":
    main()
