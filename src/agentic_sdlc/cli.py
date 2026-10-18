"""``agentic-sdlc`` command line.

Reviewer-facing entry points for both planes. The CLI assembles the same
engine the API uses (``orchestration.bootstrap``) against the configured
database, so a run started here can be inspected over HTTP and vice versa.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from agentic_sdlc.config import Settings, load_settings
from agentic_sdlc.orchestration.bootstrap import default_agents, default_planners
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.evidence import export_run
from agentic_sdlc.orchestration.metrics import aggregate, compute_run_metrics
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.workflow_store import SqlWorkflowStore
from agentic_sdlc.policy.registry import POLICY_VERSION, describe
from agentic_sdlc.scenarios import SCENARIOS
from agentic_sdlc.scenarios.runner import release_for, run_scenario
from agentic_sdlc.telemetry.logging import configure_logging

app = typer.Typer(
    help="Agentic SDLC orchestration demonstrated on a URL shortener.", no_args_is_help=True
)
workflow = typer.Typer(help="Control plane: start, inspect and govern workflow runs.")
scenario = typer.Typer(help="Replay the assessment scenarios through the real engine.")
app.add_typer(workflow, name="workflow")
app.add_typer(scenario, name="scenario")


def _engine(settings: Settings, store: SqlWorkflowStore) -> Engine:
    return Engine(
        store=store,
        agents=default_agents(settings, store),
        planners=default_planners(settings),
        settings=settings,
        policy_version=POLICY_VERSION,
    )


def _system(settings: Settings | None = None) -> tuple[Settings, Engine, SqlWorkflowStore]:
    settings = settings or load_settings()
    configure_logging(settings.log_level, settings.log_json)
    db = Database(settings.database_url)
    db.create_all()
    store = SqlWorkflowStore(db)
    return settings, _engine(settings, store), store


def _echo(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True, default=str))


def _run_summary(engine: Engine, run_id: str) -> dict[str, Any]:
    run = engine.load(run_id)
    graph = engine.graph_view(run_id)
    return {
        "run_id": run.id,
        "title": run.title,
        "scope": run.scope,
        "state": run.state.value,
        "terminal_reason": run.terminal_reason,
        "requirement_version": run.requirement_version,
        "graph_version": run.graph_version,
        "policy_version": run.policy_version,
        "open_gates": graph["open_gates"],
        "stages": {s["name"]: s.get("state", "PENDING") for s in graph["stages"]},
    }


# --- application plane ----------------------------------------------------------


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the HTTP API (both planes)."""
    import uvicorn

    uvicorn.run(
        "agentic_sdlc.api.app:create_app", host=host, port=port, reload=reload, factory=True
    )


@app.command("init-db")
def init_db() -> None:
    """Create the database schema (idempotent)."""
    settings = load_settings()
    Database(settings.database_url).create_all()
    typer.echo(f"schema ready at {settings.database_url}")


# --- control plane --------------------------------------------------------------


@workflow.command("start")
def workflow_start(
    requirement: str = typer.Argument(..., help="Requirement text, or @path/to/file.md"),
    title: str = typer.Option("", help="Short title (defaults to the first line)"),
    scope: str = typer.Option("auto", help="greenfield | brownfield | ambiguous | auto"),
    run: bool = typer.Option(True, help="Advance until a gate or terminal state"),
) -> None:
    """Submit a requirement to the orchestrator."""
    if requirement.startswith("@"):
        requirement = Path(requirement[1:]).read_text(encoding="utf-8")
    _, engine, _ = _system()
    run_id = engine.start(
        title=title or requirement.strip().splitlines()[0][:120],
        requirement=requirement,
        scope=scope,
    )
    if run:
        engine.run(run_id)
    _echo(_run_summary(engine, run_id))


@workflow.command("inspect")
def workflow_inspect(run_id: str, graph: bool = typer.Option(False, help="Include graph")) -> None:
    """Show run state, open gates and stage states."""
    _, engine, _ = _system()
    data = _run_summary(engine, run_id)
    if graph:
        data["graph"] = engine.graph_view(run_id)
    _echo(data)


@workflow.command("list")
def workflow_list() -> None:
    _, engine, store = _system()
    _echo([_run_summary(engine, r.id) for r in store.list_runs()])


@workflow.command("gates")
def workflow_gates(run_id: str) -> None:
    """List open human gates with the context needed to decide."""
    _, engine, _ = _system()
    _echo(engine.open_gates(run_id))


@workflow.command("decide")
def workflow_decide(
    run_id: str,
    gate: str,
    decision: str = typer.Argument(..., help="approve | reject | clarify"),
    reason: str = typer.Option(..., "--reason", "-r", help="Why (recorded verbatim)"),
    actor: str = typer.Option(..., "--actor", "-a", help="Who is deciding"),
    payload: str = typer.Option("{}", help="JSON payload (clarification answers, acks)"),
    run: bool = typer.Option(True, help="Advance after recording the decision"),
) -> None:
    """Record a human decision at an open gate."""
    _, engine, _ = _system()
    engine.decide(
        run_id,
        gate=gate,
        actor=actor,
        decision=decision,
        reason=reason,
        payload=json.loads(payload),
    )
    if run:
        engine.run(run_id)
    _echo(_run_summary(engine, run_id))


@workflow.command("run")
def workflow_run(run_id: str, max_batches: int | None = typer.Option(None)) -> None:
    """Advance a run (optionally a bounded number of batches, leaving it SUSPENDED)."""
    _, engine, _ = _system()
    engine.run(run_id, max_batches=max_batches)
    _echo(_run_summary(engine, run_id))


@workflow.command("resume")
def workflow_resume(run_id: str) -> None:
    """Resume a suspended or interrupted run from persisted state."""
    _, engine, _ = _system()
    engine.resume(run_id)
    _echo(_run_summary(engine, run_id))


@workflow.command("stop")
def workflow_stop(
    run_id: str,
    reason: str = typer.Option(..., "--reason", "-r"),
    actor: str = typer.Option(..., "--actor", "-a"),
) -> None:
    """Operator safe-stop."""
    _, engine, _ = _system()
    engine.stop(run_id, actor=actor, reason=reason)
    _echo(_run_summary(engine, run_id))


@workflow.command("replan")
def workflow_replan(
    run_id: str,
    trigger: str = typer.Option(..., "--trigger", "-t"),
    data: str = typer.Option("{}", help="JSON context updates (requirement change)"),
) -> None:
    """Apply an upstream change and replan the affected downstream stages."""
    _, engine, _ = _system()
    engine.replan(run_id, trigger=trigger, data_updates=json.loads(data))
    _echo(_run_summary(engine, run_id))


@workflow.command("events")
def workflow_events(run_id: str) -> None:
    """Print the audit trail."""
    _, engine, store = _system()
    engine.load(run_id)
    for e in store.list_events(run_id):
        typer.echo(
            f"{e.seq:4d} {e.at.isoformat()} {e.actor_type.value:6s} {e.kind.value:24s} "
            f"{(e.stage or '-'):20s} {(e.result or ''):12s} {e.reason or ''}"
        )


@workflow.command("metrics")
def workflow_metrics(run_id: str | None = typer.Argument(None)) -> None:
    """Reliability metrics for one run, or aggregated across all runs."""
    _, engine, store = _system()
    if run_id:
        engine.load(run_id)
        _echo(compute_run_metrics(store.list_events(run_id)))
    else:
        per_run = [compute_run_metrics(store.list_events(r.id)) for r in store.list_runs()]
        _echo(aggregate(per_run))


@workflow.command("release")
def workflow_release(run_id: str) -> None:
    """Release-readiness determination from persisted policy results and state."""
    _, engine, store = _system()
    engine.load(run_id)
    _echo(release_for(store, run_id))


@workflow.command("policies")
def workflow_policies() -> None:
    """List the versioned policies the compliance stage evaluates."""
    _echo({"policy_version": POLICY_VERSION, "policies": describe()})


# --- scenarios -------------------------------------------------------------------


@scenario.command("list")
def scenario_list() -> None:
    _echo(
        [
            {
                "name": s.name,
                "title": s.title,
                "scope": s.scope,
                "expected_terminal": s.expected_terminal,
                "demo_faults": s.settings,
            }
            for s in SCENARIOS.values()
        ]
    )


@scenario.command("run")
def scenario_run(
    name: str = typer.Argument(..., help="greenfield | brownfield | ambiguous | policy-fail | ..."),
    actor: str = typer.Option(..., "--actor", "-a", help="Who makes the scripted decisions"),
    decide: bool = typer.Option(
        True, help="Apply the scripted human decisions; --no-decide stops at the first gate"
    ),
    export: str | None = typer.Option(
        None, help="Export evidence into this directory under <name>/ (e.g. docs/evidence)"
    ),
) -> None:
    """Run a scenario end-to-end through the real engine with recorded human decisions."""
    try:
        chosen = SCENARIOS[name]
    except KeyError as exc:
        raise typer.BadParameter(f"unknown scenario {name!r}; see `scenario list`") from exc
    settings, _, store = _system()
    outcome = run_scenario(
        chosen,
        store=store,
        engine_factory=lambda s: _engine(s, store),
        base_settings=settings,
        actor=actor,
        decide=decide,
    )
    result = outcome.to_dict()
    if export:
        engine = _engine(settings, store)
        result["export"] = export_run(
            engine,
            store,
            outcome.run_id,
            Path(export),
            label=name,
            extra={
                "scenario": chosen.name,
                "title": chosen.title,
                "description": chosen.description,
                "requirement": chosen.requirement,
                "scope": chosen.scope,
                "demo_faults": chosen.settings,
                "expected_terminal": chosen.expected_terminal,
                "outcome": {k: v for k, v in result.items() if k != "export"},
                "note": "Scripted decisions were recorded through Engine.decide by the named "
                "actor; demonstration faults are injected via Settings and labelled.",
            },
        )
    _echo(result)


@workflow.command("export-evidence")
def workflow_export(
    run_id: str,
    out: str = typer.Option("docs/evidence", help="Output directory"),
) -> None:
    """Export persisted run records as reviewer evidence."""
    _, engine, store = _system()
    _echo(export_run(engine, store, run_id, Path(out)))


if __name__ == "__main__":  # pragma: no cover
    app()
