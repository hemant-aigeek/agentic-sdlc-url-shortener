"""Analysis agents: impact analysis, decomposition, design (FR-O16..O18, SCN-B, ADR-010).

``ImpactAnalysisAgent`` is the brownfield differentiator: it derives search
terms from the normalised requirement, scans the *actual* repository and
reports impacted modules, interfaces (OpenAPI paths), data flows, tests,
documentation, regression risks and rollback considerations — before any
change is allowed (policy CHG-001 checks that ordering).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import StageError
from agentic_sdlc.orchestration.agents.base import Agent, StageResult
from agentic_sdlc.orchestration.context import RunContext

# requirement vocabulary -> (search terms in code, component hint, regression risk, note)
TERMS: dict[str, dict[str, Any]] = {
    "expire": {
        "search": ["expir", "GoneError", "410"],
        "components": ["domain/service.py", "api/routers/redirect.py", "errors.py"],
        "risk": "clients that branch on the expired-link status code or on expires_at semantics",
    },
    "410": {
        "search": ["GoneError", "410", "NotFoundError"],
        "components": ["api/routers/redirect.py", "api/problems.py", "errors.py"],
        "risk": "status-code contract change is visible to every redirect consumer",
    },
    "404": {
        "search": ["NotFoundError", "404"],
        "components": ["api/problems.py", "errors.py"],
        "risk": "not-found handling is shared by links, analytics and workflow routes",
    },
    "analytics": {
        "search": ["analytics", "RedirectEvent", "redirect_event", "per_day"],
        "components": [
            "domain/service.py",
            "persistence/link_repository.py",
            "api/routers/links.py",
            "api/schemas.py",
        ],
        "risk": "per-day grouping and best-effort recording (AMB-05) must keep their semantics",
    },
    "redirect": {
        "search": ["resolve", "redirect"],
        "components": ["api/routers/redirect.py", "domain/service.py"],
        "risk": "the redirect path is the hot path; latency target NFR-06",
    },
    "valid": {
        "search": ["validat", "ALLOWED_SCHEMES", "_BLOCKED_NETWORKS"],
        "components": ["domain/validation.py"],
        "risk": "any change here is security-sensitive (SEC-001)",
    },
    "scheme": {
        "search": ["ALLOWED_SCHEMES"],
        "components": ["domain/validation.py"],
        "risk": "allow-list is a security control (SEC-001)",
    },
    "code": {
        "search": ["generate_code", "short_code", "SHORT_CODE"],
        "components": ["domain/codes.py", "domain/service.py"],
        "risk": "uniqueness and unpredictability (FR-U04)",
    },
    "health": {
        "search": ["health", "readiness"],
        "components": ["api/routers/health.py"],
        "risk": "readiness is used by operators to gate traffic",
    },
    "idempot": {
        "search": ["idempotency"],
        "components": ["domain/service.py", "api/routers/links.py"],
        "risk": "same key + different payload must stay a conflict (FR-U09)",
    },
    "rate limit": {
        "search": ["TokenBucket", "rate_limit"],
        "components": ["api/ratelimit.py"],
        "risk": "limiter is in-process; behaviour differs per worker",
    },
    "endpoint": {
        "search": ["APIRouter", "@router"],
        "components": ["api/routers/links.py", "api/app.py"],
        "risk": "new routes must be reflected in the versioned OpenAPI contract (CHG-002)",
    },
}

LAYER_ORDER = ("api/", "domain/", "persistence/", "policy/", "orchestration/", "telemetry/")
SKIP_DIRS = {".git", ".venv", "venv", "data", "node_modules", "__pycache__", ".hypothesis"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt"}


def requirement_terms(normalized: dict[str, Any]) -> list[str]:
    text = " ".join(normalized.get("functional_statements", [])).lower()
    return [t for t in TERMS if t in text]


def _iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in TEXT_SUFFIXES:
                out.append(p)
    return sorted(out)


def _openapi_paths(root: Path, needles: list[str]) -> list[str]:
    spec = root / "specs" / "001-agentic-url-shortener" / "contracts" / "openapi.yaml"
    if not spec.exists():
        return []
    paths: list[str] = []
    current: str | None = None
    block: list[str] = []
    for line in [*spec.read_text(encoding="utf-8").splitlines(), "  /__end__:"]:
        m = re.match(r"^  (/\S*):\s*$", line)
        if m:
            if current and any(n.lower() in "\n".join(block).lower() for n in needles):
                paths.append(current)
            current, block = m.group(1), []
        elif current:
            block.append(line)
    return [p for p in paths if p != "/__end__"]


def _layer(path: str) -> int:
    for i, layer in enumerate(LAYER_ORDER):
        if f"/{layer}" in path:
            return i
    return len(LAYER_ORDER)


@dataclass
class ImpactAnalysisAgent(Agent):
    settings: Settings
    name: str = "impact_analysis"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        normalized = ctx.data.get("normalized")
        if not normalized:
            raise StageError("impact_analysis requires the normalized requirement")
        scope = ctx.data.get("scope", ctx.scope)
        if scope != "brownfield":
            return StageResult(
                output={"applicable": False, "reason": f"scope is {scope}; nothing to change"},
                artifacts=[("impact_analysis", {"applicable": False, "scope": scope})],
            )
        terms = requirement_terms(normalized)
        needles = sorted({n for t in terms for n in TERMS[t]["search"]})
        root = self.settings.repository_root.resolve()
        files = _iter_files(root)
        modules: dict[str, list[str]] = {}
        tests: dict[str, list[str]] = {}
        docs: dict[str, list[str]] = {}
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits = [n for n in needles if n.lower() in text.lower()]
            if not hits:
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith("src/"):
                modules[rel] = hits
            elif rel.startswith("tests/"):
                tests[rel] = hits
            elif rel.endswith((".md", ".yaml", ".yml")) and not rel.startswith(".specify"):
                docs[rel] = hits
        app_plane = sorted(
            (m for m in modules if "/orchestration/" not in m and "/policy/" not in m),
            key=lambda m: (_layer(m), m),
        )
        flows = [" → ".join(group) for group in _group_flows(app_plane)]
        risks = sorted({TERMS[t]["risk"] for t in terms})
        schema_change = any(
            k in " ".join(normalized["functional_statements"]).lower()
            for k in ("field", "column", "store ", "persist")
        )
        artifact = {
            "applicable": True,
            "scope": scope,
            "requirement_version": normalized.get("version", ctx.requirement_version),
            "terms": terms,
            "search_needles": needles,
            "impacted_modules": app_plane,
            "impacted_control_plane_modules": sorted(set(modules) - set(app_plane)),
            "impacted_interfaces": _openapi_paths(root, needles),
            "impacted_data_flows": flows,
            "impacted_tests": sorted(tests),
            "impacted_docs": sorted(docs),
            "regression_risks": risks,
            "data_compatibility": "schema change expected; migration and down-migration required"
            if schema_change
            else "no persistence schema change; stored rows remain valid",
            "rollback_considerations": [
                "change set is applied to the run workspace and is fully reversible (rollback)",
                "an API status-code or shape change is backward-incompatible for consumers; "
                "announce via the versioned contract (CHG-002)",
                "no data migration" if not schema_change else "down-migration must be tested",
            ],
            "evidence": {
                "repository_root": str(root),
                "files_scanned": len(files),
                "files_matched": len(modules) + len(tests) + len(docs),
                "match_detail": {**modules, **tests, **docs},
            },
        }
        return StageResult(
            output={
                "applicable": True,
                "impacted_modules": app_plane,
                "impacted_tests": sorted(tests),
                "impacted_interfaces": artifact["impacted_interfaces"],
                "files_scanned": len(files),
            },
            artifacts=[("impact_analysis", artifact)],
            data_updates={"impact": {"modules": app_plane, "tests": sorted(tests)}},
        )


def _group_flows(modules: list[str]) -> list[list[str]]:
    """Order impacted application modules into request-path flows (api → domain → persistence)."""
    by_layer: dict[int, list[str]] = {}
    for m in modules:
        by_layer.setdefault(_layer(m), []).append(m)
    api = by_layer.get(0, [])
    rest = [m for i in sorted(by_layer) if i > 0 for m in by_layer[i]]
    if not api:
        return [rest] if rest else []
    return [[a, *rest] for a in api]


# --- decomposition ------------------------------------------------------------------


def _components_for(normalized: dict[str, Any], ctx: RunContext) -> list[str]:
    impact = ctx.data.get("impact", {}).get("modules")
    if impact:
        return [m.removeprefix("src/agentic_sdlc/") for m in impact]
    comps: list[str] = []
    for t in requirement_terms(normalized):
        for c in TERMS[t]["components"]:
            if c not in comps:
                comps.append(c)
    return comps or ["api/routers/links.py", "domain/service.py"]


@dataclass
class DecomposeAgent(Agent):
    settings: Settings
    name: str = "decompose"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        normalized = ctx.data.get("normalized")
        if not normalized:
            raise StageError("decompose requires the normalized requirement")
        components = _components_for(normalized, ctx)
        tasks: list[dict[str, Any]] = []
        impl_ids: list[str] = []
        for i, ac in enumerate(normalized["acceptance_criteria"], start=1):
            comp = [components[(i - 1) % len(components)]] if components else []
            test_id, impl_id = f"T{i:02d}-test", f"T{i:02d}-impl"
            tasks.append(
                {
                    "id": test_id,
                    "kind": "test",
                    "objective": f"Write a failing test for {ac['id']}: {ac['statement']}",
                    "criterion": ac["id"],
                    "depends_on": [],
                    "parallel": True,
                    "components": [f"tests for {c}" for c in comp],
                    "acceptance": ac["observable"],
                    "tdd": "red",
                }
            )
            tasks.append(
                {
                    "id": impl_id,
                    "kind": "implement",
                    "objective": f"Implement the smallest change satisfying {ac['id']}",
                    "criterion": ac["id"],
                    "depends_on": [test_id],
                    "parallel": False,
                    "components": comp,
                    "acceptance": f"{test_id} passes; regression suite green",
                    "tdd": "green",
                }
            )
            impl_ids.append(impl_id)
        # implementation tasks touching disjoint components may run in parallel
        seen: dict[str, str] = {}
        for t in tasks:
            if t["kind"] != "implement":
                continue
            key = ",".join(t["components"])
            if key in seen:
                t["depends_on"].append(seen[key])
                t["parallel"] = False
            else:
                seen[key] = t["id"]
                t["parallel"] = True
        tasks.append(
            {
                "id": "T90-docs",
                "kind": "docs",
                "objective": "Update API documentation, contract and README for the change",
                "criterion": "ALL",
                "depends_on": list(impl_ids),
                "parallel": False,
                "components": ["specs/contracts/openapi.yaml", "README.md"],
                "acceptance": "contract drift check passes; docs describe new behaviour",
                "tdd": "n/a",
            }
        )
        tasks.append(
            {
                "id": "T99-verify",
                "kind": "verify",
                "objective": "Run the regression suite and the impacted test targets",
                "criterion": "ALL",
                "depends_on": [*impl_ids, "T90-docs"],
                "parallel": False,
                "components": ["tests/"],
                "acceptance": "exit code 0",
                "tdd": "refactor",
            }
        )
        artifact = {
            "requirement_version": normalized.get("version", ctx.requirement_version),
            "components": components,
            "tasks": tasks,
            "critical_path": [t["id"] for t in tasks if not t["parallel"]],
            "parallel_tasks": [t["id"] for t in tasks if t["parallel"]],
        }
        return StageResult(
            output={
                "tasks": len(tasks),
                "parallel_tasks": artifact["parallel_tasks"],
                "components": components,
            },
            artifacts=[("decomposition", artifact)],
            data_updates={"components": components, "decomposition_tasks": tasks},
        )


# --- design -------------------------------------------------------------------------


_STATUS = re.compile(r"\b([2-5]\d\d)\b")
_PATH = re.compile(r"(/api/v1/\S+|/\{code\})")


@dataclass
class DesignAgent(Agent):
    settings: Settings
    name: str = "design"
    new_dependencies: list[dict[str, str]] = field(default_factory=list)

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        normalized = ctx.data.get("normalized")
        if not normalized:
            raise StageError("design requires the normalized requirement")
        statements: list[str] = normalized["functional_statements"]
        text = " ".join(statements)
        components = ctx.data.get("components") or _components_for(normalized, ctx)
        api_changes: list[dict[str, str]] = []
        for s in statements:
            codes = _STATUS.findall(s)
            paths = _PATH.findall(s)
            lower = s.lower()
            if paths or "endpoint" in lower:
                api_changes.append(
                    {
                        "path": paths[0].rstrip(".,")
                        if paths
                        else "(new route, path per decomposition)",
                        "change": "add"
                        if any(w in lower for w in ("add", "new", "expose"))
                        else "modify",
                        "detail": s,
                    }
                )
            elif codes and any(w in lower for w in ("return", "respond", "status")):
                api_changes.append(
                    {
                        "path": "/{code}"
                        if "redirect" in lower or "link" in lower
                        else "(affected route)",
                        "change": "status-code",
                        "detail": f"status {' / '.join(codes)}: {s}",
                    }
                )
        schema_change = any(k in text.lower() for k in ("field", "column", "store ", "persist"))
        impact = bool(api_changes) or schema_change
        design = {
            "requirement_version": normalized.get("version", ctx.requirement_version),
            "components": components,
            "api_changes": api_changes,
            "schema_changes": ["persistence schema change required"] if schema_change else [],
            "api_or_schema_impact": impact,
            "contract_version_impact": "minor (additive)"
            if any(c["change"] == "add" for c in api_changes)
            else ("breaking for consumers" if api_changes else "none"),
            "new_dependencies": list(self.new_dependencies),
            "decisions": [
                "Keep the change inside existing module boundaries (ADR-001)",
                "No new runtime dependency; stdlib + existing stack (ADR-002)",
                "Contract exported and drift-checked before approval (CHG-002)",
            ],
            "trade_offs": [
                "Smallest change that satisfies the acceptance criteria over a broader refactor",
                "Backward compatibility is traded for correctness where a status code changes",
            ],
            "risks": [
                "Consumer breakage on contract changes",
                "Regression in the shared not-found / gone handling",
            ],
            "validation": "contract tests + impacted regression targets executed by verify",
        }
        return StageResult(
            output={
                "api_or_schema_impact": impact,
                "api_changes": len(api_changes),
                "schema_change": schema_change,
                "components": components,
                "contract_version_impact": design["contract_version_impact"],
            },
            artifacts=[("design", design)],
            data_updates={"api_or_schema_impact": impact},
        )
