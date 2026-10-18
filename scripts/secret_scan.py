"""Secret-pattern scan over tracked files (constitution V, policy SEC-002).

Deliberately small: a handful of high-signal patterns rather than a full
secret-scanning product. Findings are printed with path:line and the process
exits 1. The same patterns are reused by the policy evaluator for workflow
artifacts, so the repository check and the orchestration check agree.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic-api-key": re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\b\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]"
    ),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}

ALLOWLIST_PATHS = {"scripts/secret_scan.py"}


def scan_text(text: str) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                hits.append((name, lineno))
    return hits


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True, text=True
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if str(path) in ALLOWLIST_PATHS or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, lineno in scan_text(text):
            findings.append(f"{path}:{lineno}: {name}")
    if findings:
        print("secret patterns found:")
        print("\n".join(findings))
        return 1
    print("no secret patterns found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
