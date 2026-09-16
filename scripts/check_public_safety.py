#!/usr/bin/env python3
"""Fail when public RA-PSI content contains obvious credentials or secret files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SECRET_FILE_NAMES = {
    "client_secret.json",
    "credentials.json",
    "gmail-token.json",
    "config.local.json",
    ".env",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(
        r"(?i)[\"']?(?:api[_-]?key|client_secret|refresh_token|access_token)[\"']?"
        r"\s*[=:]\s*[\"'](?!YOUR_|REDACTED|<)[^\"']{20,}[\"']"
    ),
)
SKIP_PARTS = {".git", "__pycache__", "bridge_state"}


def scan_tree(root: Path) -> list[str]:
    findings: list[str] = []
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.name.lower() in SECRET_FILE_NAMES:
            findings.append(f"secret-like filename: {path.relative_to(root)}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"secret-like content: {path.relative_to(root)} ({pattern.pattern})")
    return findings


def main(argv: list[str] | None = None) -> int:
    root = Path((argv or sys.argv[1:])[0]) if (argv or sys.argv[1:]) else Path(__file__).resolve().parents[1]
    findings = scan_tree(root)
    if findings:
        print("PUBLIC SAFETY FAILED")
        print("\n".join(findings))
        return 1
    print(f"PUBLIC SAFETY OK: {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
