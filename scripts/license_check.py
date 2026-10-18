"""Dependency licence allow-list (policy DEP-001, advisory).

Runs ``pip-licenses`` over the active environment and fails if any installed
distribution has a licence outside the allow-list. Unknown licences are
reported but do not fail the check, because metadata quality varies; they are
listed so a human can decide.
"""

from __future__ import annotations

import json
import subprocess
import sys

ALLOWED = {
    "MIT",
    "MIT License",
    "BSD",
    "BSD License",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache 2.0",
    "Apache-2.0",
    "Apache Software License",
    "Apache License 2.0",
    "ISC",
    "ISC License (ISCL)",
    "Python Software Foundation License",
    "PSF-2.0",
    "MPL-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "The Unlicense (Unlicense)",
    "Unlicense",
    "0BSD",
}


def main() -> int:
    raw = subprocess.run(
        ["pip-licenses", "--format=json", "--with-system"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows = json.loads(raw)
    disallowed: list[str] = []
    unknown: list[str] = []
    for row in rows:
        name, licence = row["Name"], row["License"]
        parts = [
            p.strip()
            for p in licence.replace(";", ",").replace(" OR ", ",").replace(" AND ", ",").split(",")
        ]
        if licence in {"UNKNOWN", ""}:
            unknown.append(name)
        elif not any(p in ALLOWED for p in parts):
            disallowed.append(f"{name}: {licence}")
    if unknown:
        print("licence unknown (review manually):", ", ".join(sorted(unknown)))
    if disallowed:
        print("licences outside allow-list:")
        print("\n".join(sorted(disallowed)))
        return 1
    print(f"{len(rows)} distributions checked; all licences allow-listed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
