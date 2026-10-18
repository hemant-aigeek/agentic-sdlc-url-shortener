"""Control-plane API: create and inspect workflow runs, resume, stop, replan.

All mutating routes require the API key; inspection routes do too, since run
context may contain requirement text. Decisions live in ``decisions.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from agentic_sdlc.api.auth import require_actor, require_api_key
from agentic_sdlc.api.workflow_schemas import (
    ArtifactView,
    AuditEventView,
    GraphView,
    StopRequest,
    WorkflowCreateRequest,
    WorkflowRunView,
)
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.store import RunRecord, WorkflowStore

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def get_engine(request: Request) -> Engine:
    return request.app.state.engine  # type: ignore[no-any-return]


def get_store(request: Request) -> WorkflowStore:
    return request.app.state.workflow_store  # type: ignore[no-any-return]


def _view(engine: Engine, run: RunRecord) -> WorkflowRunView:
    graph = engine.graph_view(run.id)
    return WorkflowRunView(
        id=run.id,
        title=run.title,
        scope=run.scope,
        state=run.state.value,
        requirement_version=run.requirement_version,
        graph_version=run.graph_version,
        policy_version=run.policy_version,
        created_at=run.created_at,
        updated_at=run.updated_at,
        terminal_reason=run.terminal_reason,
        open_gates=graph["open_gates"],
        stage_states={s["name"]: s.get("state", "PENDING") for s in graph["stages"]},
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WorkflowRunView)
def create_workflow(
    body: WorkflowCreateRequest,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
) -> WorkflowRunView:
    run_id = engine.start(
        title=body.title,
        requirement=body.requirement,
        scope=body.scope,
        planner=body.planner,
        data=body.data,
    )
    run = engine.run(run_id) if body.run else engine.load(run_id)
    return _view(engine, run)


@router.get("", response_model=list[WorkflowRunView])
def list_workflows(
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
    store: WorkflowStore = Depends(get_store),  # noqa: B008
) -> list[WorkflowRunView]:
    return [_view(engine, run) for run in store.list_runs()]


@router.get("/{run_id}", response_model=WorkflowRunView)
def get_workflow(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
) -> WorkflowRunView:
    return _view(engine, engine.load(run_id))


@router.get("/{run_id}/graph", response_model=GraphView)
def get_graph(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
) -> dict[str, Any]:
    return engine.graph_view(run_id)


@router.get("/{run_id}/events", response_model=list[AuditEventView])
def get_events(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
    store: WorkflowStore = Depends(get_store),  # noqa: B008
) -> list[dict[str, Any]]:
    engine.load(run_id)  # 404 if unknown
    return [e.to_dict() for e in store.list_events(run_id)]


@router.get("/{run_id}/artifacts", response_model=list[ArtifactView])
def get_artifacts(
    run_id: str,
    include_invalidated: bool = False,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
    store: WorkflowStore = Depends(get_store),  # noqa: B008
) -> list[ArtifactView]:
    engine.load(run_id)
    return [
        ArtifactView(
            id=a.id,
            stage=a.stage,
            kind=a.kind,
            version=a.version,
            derived_from=a.derived_from,
            policy_version=a.policy_version,
            invalidated=a.invalidated,
            created_at=a.created_at,
            content=a.content,
        )
        for a in store.list_artifacts(run_id, include_invalidated=include_invalidated)
    ]


@router.get("/{run_id}/lineage")
def get_lineage(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
    store: WorkflowStore = Depends(get_store),  # noqa: B008
) -> dict[str, Any]:
    """Walk derived_from from every live artifact back to the requirement (FR-O07)."""
    run = engine.load(run_id)
    arts = {a.id: a for a in store.list_artifacts(run_id)}
    nodes = [
        {
            "id": a.id,
            "kind": a.kind,
            "stage": a.stage,
            "version": a.version,
            "invalidated": a.invalidated,
            "derived_from": a.derived_from,
        }
        for a in arts.values()
    ]
    return {
        "run_id": run_id,
        "requirement_version": run.requirement_version,
        "policy_version": run.policy_version,
        "decisions": run.context.decisions,
        "artifacts": nodes,
    }


@router.post("/{run_id}/resume", response_model=WorkflowRunView)
def resume_workflow(
    run_id: str,
    _: str = Depends(require_api_key),
    engine: Engine = Depends(get_engine),  # noqa: B008
) -> WorkflowRunView:
    return _view(engine, engine.resume(run_id))


@router.post("/{run_id}/stop", response_model=WorkflowRunView)
def stop_workflow(
    run_id: str,
    body: StopRequest,
    actor: str = Depends(require_actor),
    engine: Engine = Depends(get_engine),  # noqa: B008
) -> WorkflowRunView:
    return _view(engine, engine.stop(run_id, actor=actor, reason=body.reason))
