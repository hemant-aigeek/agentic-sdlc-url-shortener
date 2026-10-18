"""Reliability and orchestration measurements (FR-O19) and the policy catalogue (FR-G06)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from agentic_sdlc.api.auth import require_api_key
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.metrics import aggregate, compute_run_metrics
from agentic_sdlc.orchestration.store import WorkflowStore

router = APIRouter(prefix="/api/v1", tags=["metrics"])


def _engine(request: Request) -> Engine:
    return request.app.state.engine  # type: ignore[no-any-return]


def _store(request: Request) -> WorkflowStore:
    return request.app.state.workflow_store  # type: ignore[no-any-return]


@router.get("/metrics")
def all_metrics(
    _: str = Depends(require_api_key),
    store: WorkflowStore = Depends(_store),  # noqa: B008
) -> dict[str, Any]:
    per_run = {run.id: compute_run_metrics(store.list_events(run.id)) for run in store.list_runs()}
    return {"aggregate": aggregate(per_run.values()), "runs": per_run}


@router.get("/workflows/{run_id}/metrics")
def run_metrics(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(_engine),  # noqa: B008
    store: WorkflowStore = Depends(_store),  # noqa: B008
) -> dict[str, Any]:
    engine.load(run_id)
    return compute_run_metrics(store.list_events(run_id))


@router.get("/policies")
def policies(_: str = Depends(require_api_key)) -> dict[str, Any]:
    from agentic_sdlc.policy.registry import POLICY_VERSION, describe

    return {"policy_version": POLICY_VERSION, "policies": describe()}
