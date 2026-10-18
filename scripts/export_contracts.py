"""Export (or verify) the versioned API contract and JSON schemas (plan §2, CHG-002).

    python scripts/export_contracts.py          # write contracts
    python scripts/export_contracts.py --check  # exit 1 if the committed files drift

The committed files are the reviewed contract. Any behaviour change that alters
them shows up as a diff in a commit, which is what makes API/schema changes
reviewable and subject to change control.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "001-agentic-url-shortener" / "contracts"
SCHEMAS = CONTRACTS / "schemas"


def _build() -> tuple[str, dict[str, str]]:
    from agentic_sdlc.api import schemas as app_schemas
    from agentic_sdlc.api.app import create_app
    from agentic_sdlc.config import Settings

    app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:", log_json=False))
    openapi = app.openapi()
    openapi_yaml = yaml.safe_dump(openapi, sort_keys=True, allow_unicode=True)

    exported: dict[str, str] = {}
    models = [
        app_schemas.LinkCreateRequest,
        app_schemas.LinkResponse,
        app_schemas.AnalyticsResponse,
        app_schemas.Problem,
    ]
    try:
        from agentic_sdlc.api import workflow_schemas  # added in G4

        models.extend(workflow_schemas.EXPORTED)
    except ImportError:
        pass
    for model in models:
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        exported[f"{model.__name__}.json"] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    return openapi_yaml, exported


def main(check: bool) -> int:
    openapi_yaml, exported = _build()
    files: dict[Path, str] = {CONTRACTS / "openapi.yaml": openapi_yaml}
    files.update({SCHEMAS / name: body for name, body in exported.items()})
    if check:
        drift = [
            str(p.relative_to(ROOT))
            for p, body in files.items()
            if not p.exists() or p.read_text(encoding="utf-8") != body
        ]
        if drift:
            print("contract drift detected; run scripts/export_contracts.py and review the diff:")
            print("\n".join(drift))
            return 1
        print(f"{len(files)} contract files match the application")
        return 0
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    for p, body in files.items():
        p.write_text(body, encoding="utf-8")
        print("wrote", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
