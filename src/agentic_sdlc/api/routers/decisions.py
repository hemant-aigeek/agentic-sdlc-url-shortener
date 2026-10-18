"""Human gate API (FR-G02, FR-G03): list open gates and record a decision.

A decision needs an attributable actor (``X-Actor``) in addition to the API
key; the engine refuses anything that is not approve / reject / clarify on an
open gate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from agentic_sdlc.api.auth import require_actor, require_api_key
from agentic_sdlc.api.workflow_schemas import DecisionRequest, DecisionView, GateView
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.store import WorkflowStore

router = APIRouter(prefix="/api/v1/workflows/{run_id}", tags=["decisions"])


def _engine(request: Request) -> Engine:
    return request.app.state.engine  # type: ignore[no-any-return]


def _store(request: Request) -> WorkflowStore:
    return request.app.state.workflow_store  # type: ignore[no-any-return]


@router.get("/gates", response_model=list[GateView])
def list_gates(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(_engine),  # noqa: B008
) -> list[GateView]:
    return [GateView(**g) for g in engine.open_gates(run_id)]


@router.get("/decisions", response_model=list[DecisionView])
def list_decisions(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(_engine),  # noqa: B008
    store: WorkflowStore = Depends(_store),  # noqa: B008
) -> list[DecisionView]:
    engine.load(run_id)
    return [DecisionView(**vars(d)) for d in store.list_decisions(run_id)]


@router.post(
    "/gates/{gate}/decision", status_code=status.HTTP_201_CREATED, response_model=DecisionView
)
def decide(
    run_id: str,
    gate: str,
    body: DecisionRequest,
    actor: str = Depends(require_actor),
    engine: Engine = Depends(_engine),  # noqa: B008
    store: WorkflowStore = Depends(_store),  # noqa: B008
) -> DecisionView:
    engine.decide(
        run_id,
        gate=gate,
        actor=actor,
        decision=body.decision,
        reason=body.reason,
        payload=body.payload,
    )
    if body.run:
        engine.run(run_id)
    latest = store.list_decisions(run_id)[-1]
    return DecisionView(**vars(latest))
