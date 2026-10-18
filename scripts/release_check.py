"""Release-readiness check for the repository (FR-G10, constitution V and VI).

Runs every repository-level control and writes a machine-readable record to
``docs/evidence/release-check.json``:

1. quality gate (ruff, mypy, pytest, contract drift, secret scan, licences)
2. dependency vulnerability audit (pip-audit; recorded as SKIPPED when the
   advisory database is unreachable, never silently passed)
3. policy registry summary (version + mandatory/advisory split)
4. scenario evidence presence (the three scenarios and the demonstrations)

Exit status is non-zero when any mandatory control fails. The decision uses
the same three-way vocabulary as the orchestrator: READY, READY WITH ACCEPTED
LIMITATIONS, NOT READY.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "release-check.json"
REQUIRED_EVIDENCE = ("greenfield", "brownfield", "ambiguous", "policy-fail", "rejection", "resume")


def run(cmd: list[str], *, timeout: float = 900) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return {"command": " ".join(cmd), "status": "SKIPPED", "detail": "tool not installed"}
    except subprocess.TimeoutExpired:
        return {"command": " ".join(cmd), "status": "FAIL", "detail": f"timed out after {timeout}s"}
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
    return {
        "command": " ".join(cmd),
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "duration_s": round(time.monotonic() - started, 2),
        "output_tail": tail,
    }


def pip_audit() -> dict[str, Any]:
    if shutil.which("pip-audit") is None:
        return {"command": "pip-audit", "status": "SKIPPED", "detail": "pip-audit not installed"}
    result = run(["pip-audit", "--progress-spinner", "off", "--skip-editable"], timeout=300)
    joined = "\n".join(result.get("output_tail", []))
    if result["status"] == "FAIL" and (
        "Connection" in joined or "Max retries" in joined or "Temporary failure" in joined
    ):
        result["status"] = "SKIPPED"
        result["detail"] = (
            "advisory database unreachable from this environment (recorded, not passed)"
        )
    return result


def policy_summary() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from agentic_sdlc.policy.registry import POLICIES, POLICY_VERSION

    return {
        "policy_version": POLICY_VERSION,
        "mandatory": [p.id for p in POLICIES if p.mandatory],
        "advisory": [p.id for p in POLICIES if not p.mandatory],
        "exceptionable": [p.id for p in POLICIES if p.exceptionable],
    }


def evidence_presence() -> dict[str, Any]:
    present: dict[str, Any] = {}
    for name in REQUIRED_EVIDENCE:
        d = ROOT / "docs" / "evidence" / name
        run_json = d / "run.json"
        if run_json.exists():
            data = json.loads(run_json.read_text(encoding="utf-8"))
            present[name] = {"state": data["state"], "terminal_reason": data["terminal_reason"]}
        else:
            present[name] = None
    missing = [n for n, v in present.items() if v is None]
    return {"status": "PASS" if not missing else "FAIL", "scenarios": present, "missing": missing}


def main() -> int:
    checks = {
        "quality_gate": run(["bash", "scripts/check.sh"]),
        "dependency_audit": pip_audit(),
        "scenario_evidence": evidence_presence(),
    }
    mandatory_failed = [
        k for k in ("quality_gate", "scenario_evidence") if checks[k]["status"] != "PASS"
    ]
    skipped = [k for k, v in checks.items() if v["status"] == "SKIPPED"]
    if mandatory_failed:
        decision = "NOT READY"
    elif skipped or checks["dependency_audit"]["status"] != "PASS":
        decision = "READY WITH ACCEPTED LIMITATIONS"
    else:
        decision = "READY"
    record = {
        "checked_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "decision": decision,
        "mandatory_failed": mandatory_failed,
        "limitations": skipped,
        "checks": checks,
        "policies": policy_summary(),
        "measurement_type": "demonstration",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in checks.items()}, indent=2))
    print(f"release check: {decision} -> {OUT.relative_to(ROOT)}")
    return 0 if not mandatory_failed else 1


if __name__ == "__main__":
    sys.exit(main())
