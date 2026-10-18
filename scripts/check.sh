#!/usr/bin/env bash
# Quality gate. Everything a reviewer needs to trust the repository runs here.
# Exit non-zero on the first failure so CI-equivalence is unambiguous.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }

step "ruff: lint"
ruff check src tests scripts

step "ruff: format"
ruff format --check src tests scripts

step "mypy: strict on src/"
mypy

step "pytest"
pytest -q -p no:warnings "${@}"

step "contract: OpenAPI drift"
if [ -f scripts/export_contracts.py ]; then
  python scripts/export_contracts.py --check
else
  echo "skipped (contracts not generated yet)"
fi

step "secrets: pattern scan"
python scripts/secret_scan.py

step "licences: allow-list"
if command -v pip-licenses >/dev/null 2>&1; then
  python scripts/license_check.py
else
  echo "skipped (pip-licenses not installed)"
fi

printf '\n\033[1;32mALL CHECKS PASSED\033[0m\n'
