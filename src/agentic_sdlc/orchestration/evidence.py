"""Evidence export (constitution XI, SC-02).

Writes everything a reviewer needs to verify a run — state, graph, events,
artifacts, decisions, policy results, replans and metrics — as JSON files plus
a human-readable summary. The export is a copy of persisted records, never a
narrative written by an agent; and every measurement carries its
demonstration label.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.metrics import compute_run_metrics
from agentic_sdlc.orchestration.store import WorkflowStore


def _dump(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def export_run(
    engine: Engine,
    store: WorkflowStore,
    run_id: str,
    out_dir: Path,
    *,
    label: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = engine.load(run_id)
    out = out_dir / (label or run_id)
    out.mkdir(parents=True, exist_ok=True)

    graph = engine.graph_view(run_id)
    events = [e.to_dict() for e in store.list_events(run_id)]
    artifacts = [vars(a) for a in store.list_artifacts(run_id)]
    decisions = [vars(d) for d in store.list_decisions(run_id)]
    replans = [vars(r) for r in store.list_replans(run_id)]
    policy = {
        "policy_version": run.policy_version,
        "evaluations": [vars(p) for p in store.list_policy_evaluations(run_id)],
        "exceptions": [vars(x) for x in store.list_policy_exceptions(run_id)],
    }
    metrics = compute_run_metrics(store.list_events(run_id))

    run_doc = {
        "id": run.id,
        "title": run.title,
        "scope": run.scope,
        "state": run.state.value,
        "terminal_reason": run.terminal_reason,
        "requirement_version": run.requirement_version,
        "graph_version": run.graph_version,
        "policy_version": run.policy_version,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "context": run.context.to_dict(),
        "exported_at": datetime.now(UTC),
        "evidence_type": "executed run export (demonstration data)",
    }
    _dump(out / "run.json", run_doc)
    _dump(out / "graph.json", graph)
    _dump(out / "events.json", events)
    _dump(out / "artifacts.json", artifacts)
    _dump(out / "decisions.json", decisions)
    _dump(out / "replans.json", replans)
    _dump(out / "policy.json", policy)
    _dump(out / "metrics.json", metrics)
    if extra:
        _dump(out / "scenario.json", extra)
    (out / "README.md").write_text(
        _summary_markdown(run_doc, graph, events, decisions, replans, policy, metrics),
        encoding="utf-8",
    )
    return {"run_id": run_id, "path": str(out), "files": sorted(p.name for p in out.iterdir())}


def _summary_markdown(
    run: dict[str, Any],
    graph: dict[str, Any],
    events: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    replans: list[dict[str, Any]],
    policy: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    lines = [
        f"# Run {run['id']} — {run['title']}",
        "",
        "> Executed run export. Measurements are **demonstration data** from a local,",
        "> single-process run with deterministic agents; not production statistics.",
        "",
        f"- Scope: `{run['scope']}`  ·  State: `{run['state']}`"
        + (f"  ·  Reason: {run['terminal_reason']}" if run["terminal_reason"] else ""),
        f"- Requirement version: {run['requirement_version']}  ·  Graph version: {run['graph_version']}  ·  Policy version: {run['policy_version']}",
        f"- Events: {len(events)}  ·  Decisions: {len(decisions)}  ·  Replans: {len(replans)}",
        "",
        "## Stages",
        "",
        "| stage | owner | state | attempt | parallel group | fallback | depends on |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in graph["stages"]:
        lines.append(
            f"| {s['name']} | {s['owner']} | {s.get('state', 'PENDING')} | {s.get('attempt', 0)} | "
            f"{s.get('parallel_group') or ''} | {'yes' if s.get('fallback_used') else ''} | {', '.join(s['depends_on'])} |"
        )
    lines += ["", "## Human decisions", ""]
    if decisions:
        lines += ["| gate | actor | decision | reason | at |", "|---|---|---|---|---|"]
        lines += [
            f"| {d['gate']} | {d['actor']} | {d['decision']} | {d['reason']} | {d['decided_at']} |"
            for d in decisions
        ]
    else:
        lines.append("_none recorded_")
    lines += ["", "## Policy evaluations", ""]
    if policy["evaluations"]:
        lines += ["| policy | version | outcome | detail |", "|---|---|---|---|"]
        lines += [
            f"| {p['policy_id']} | {p['policy_version']} | {p['outcome']} | {p['detail']} |"
            for p in policy["evaluations"]
        ]
    else:
        lines.append("_none recorded_")
    if policy["exceptions"]:
        lines += [
            "",
            "### Policy exceptions",
            "",
            "| policy | status | approver | compensating control | expires |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {x['policy_id']} | {x['status']} | {x['approver']} | {x['compensating_control']} | {x['expires_at']} |"
            for x in policy["exceptions"]
        ]
    if replans:
        lines += ["", "## Replanning events", ""]
        for r in replans:
            lines.append(f"- {r['at']}: {r['trigger']} — invalidated {r['invalidated']}")
    rec, lat = metrics["recovery"], metrics["latency"]
    lines += [
        "",
        "## Metrics (demonstration)",
        "",
        f"- Stage success rate: {metrics['stages']['success_rate']}  ·  failure rate: {metrics['stages']['failure_rate']}",
        f"- Retries: {metrics['retries']['count']} (timeouts {metrics['retries']['timeouts']})  ·  fallbacks: {metrics['fallbacks']}  ·  compensations: {metrics['compensations']}  ·  safe-stops: {metrics['safe_stops']}  ·  replans: {metrics['replans']}",
        f"- Recovered failures: {rec['recovered_failures']}  ·  unrecovered: {rec['unrecovered_failures']} {rec['unrecovered']}",
        f"- Recovery durations (s): {rec['recovery_durations_s']}  ·  **MTTR: {rec['mttr_s']} s** ({rec['definition']})",
        f"- Latency: end-to-end {lat['end_to_end_s']} s = active {lat['active_s']} s + human wait {lat['human_wait_s']} s",
        "",
        "## Event timeline",
        "",
        "| seq | at | actor | kind | stage | attempt | result | reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in events:
        lines.append(
            f"| {e['seq']} | {e['at']} | {e['actor_type']} | {e['kind']} | {e['stage'] or ''} | "
            f"{e['attempt'] if e['attempt'] is not None else ''} | {e['result'] or ''} | {(e['reason'] or '').replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"
