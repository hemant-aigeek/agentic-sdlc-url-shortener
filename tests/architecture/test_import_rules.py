"""NFR-08 / ADR-001: import direction between planes is a tested rule, not a convention."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "agentic_sdlc"
PKG = "agentic_sdlc"

# module -> set of internal top-level modules it may import
ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "telemetry": {"config"},
    "config": set(),
    "errors": set(),
    "persistence": {"domain", "orchestration", "config", "telemetry", "errors"},
    "policy": {"orchestration", "config", "errors"},
    "orchestration": {"policy", "telemetry", "config", "errors"},
    "scenarios": {"orchestration", "policy", "config", "errors"},
    "api": {"domain", "persistence", "orchestration", "policy", "telemetry", "config", "errors", "scenarios"},
    "cli": {"api", "domain", "persistence", "orchestration", "policy", "telemetry", "config", "errors", "scenarios"},
}


def _top_module(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    return rel.parts[0] if rel.parts[0] != "__init__" else ""


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PKG):
            parts = node.module.split(".")
            if len(parts) > 1:
                found.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PKG + "."):
                    found.add(alias.name.split(".")[1])
    return found


@pytest.mark.architecture
@pytest.mark.req("NFR-08")
def test_import_direction_is_respected() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        mod = _top_module(path)
        if not mod:
            continue
        for imported in _internal_imports(path):
            if imported == mod:
                continue
            if imported not in ALLOWED.get(mod, set()):
                violations.append(f"{path.relative_to(SRC)} imports {imported}")
    assert not violations, "import-rule violations:\n" + "\n".join(violations)


@pytest.mark.architecture
@pytest.mark.req("NFR-08")
def test_nothing_imports_api_or_cli_except_cli() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        mod = _top_module(path)
        if mod in {"cli", "api", ""}:
            continue
        hit = _internal_imports(path) & {"api", "cli"}
        if hit:
            offenders.append(f"{path.relative_to(SRC)} -> {sorted(hit)}")
    assert not offenders, "\n".join(offenders)
