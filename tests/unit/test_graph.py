"""FR-O02..O04, FR-O14 / ADR-005, ADR-009: the dependency graph is an explicit, inspectable model."""

from __future__ import annotations

import pytest

from agentic_sdlc.orchestration.graph import GraphError, StageSpec, WorkflowGraph
from agentic_sdlc.orchestration.states import StageState

pytestmark = pytest.mark.unit


def spec(name: str, *deps: str, **kw: object) -> StageSpec:
    return StageSpec(name=name, agent=name, depends_on=tuple(deps), **kw)  # type: ignore[arg-type]


def diamond() -> WorkflowGraph:
    #    a
    #   / \
    #  b   c      (b, c independent -> parallel)
    #   \ /
    #    d        (join)
    return WorkflowGraph.build([spec("a"), spec("b", "a"), spec("c", "a"), spec("d", "b", "c")])


@pytest.mark.req("FR-O02")
def test_validate_rejects_cycle() -> None:
    with pytest.raises(GraphError, match="cycle"):
        WorkflowGraph.build([spec("a", "b"), spec("b", "a")])


@pytest.mark.req("FR-O02")
def test_validate_rejects_unknown_dependency() -> None:
    with pytest.raises(GraphError, match="unknown"):
        WorkflowGraph.build([spec("a", "ghost")])


@pytest.mark.req("FR-O02")
def test_validate_rejects_duplicate_stage() -> None:
    with pytest.raises(GraphError, match="duplicate"):
        WorkflowGraph.build([spec("a"), spec("a")])


@pytest.mark.req("FR-O02")
def test_topological_order_respects_dependencies() -> None:
    order = diamond().topological_order()
    assert order.index("a") < order.index("b") < order.index("d")
    assert order.index("a") < order.index("c") < order.index("d")


@pytest.mark.req("FR-O02")
def test_edges_are_explicit_and_inspectable() -> None:
    g = diamond()
    assert {(e.from_stage, e.to_stage, e.kind) for e in g.edges} == {
        ("a", "b", "hard"),
        ("a", "c", "hard"),
        ("b", "d", "hard"),
        ("c", "d", "hard"),
    }


@pytest.mark.req("FR-O03")
def test_ready_set_is_empty_until_root_succeeds_then_fans_out() -> None:
    g = diamond()
    states = dict.fromkeys(g.names(), StageState.PENDING)
    assert g.ready(states) == ["a"]
    states["a"] = StageState.SUCCEEDED
    assert g.ready(states) == ["b", "c"]  # fan-out: both independent stages ready together


@pytest.mark.req("FR-O03")
def test_join_waits_for_all_inputs() -> None:
    g = diamond()
    states = {
        "a": StageState.SUCCEEDED,
        "b": StageState.SUCCEEDED,
        "c": StageState.RUNNING,
        "d": StageState.PENDING,
    }
    assert g.ready(states) == []
    states["c"] = StageState.SUCCEEDED
    assert g.ready(states) == ["d"]


@pytest.mark.req("FR-O03", "FR-O10")
def test_fallback_counts_as_satisfied_dependency() -> None:
    g = diamond()
    states = {
        "a": StageState.SUCCEEDED,
        "b": StageState.FALLBACK,
        "c": StageState.SUCCEEDED,
        "d": StageState.PENDING,
    }
    assert g.ready(states) == ["d"]


@pytest.mark.req("FR-O03")
def test_failed_dependency_blocks_dependants() -> None:
    g = diamond()
    states = {
        "a": StageState.SUCCEEDED,
        "b": StageState.FAILED,
        "c": StageState.SUCCEEDED,
        "d": StageState.PENDING,
    }
    assert g.ready(states) == []


@pytest.mark.req("FR-O04")
def test_conditional_stage_is_skippable_and_skipped_counts_as_satisfied() -> None:
    g = WorkflowGraph.build(
        [
            spec("a"),
            spec("clarify", "a", condition=lambda ctx: ctx.get("ambiguous", False)),
            spec("b", "clarify"),
        ]
    )
    assert g.stage("clarify").is_conditional
    states = {"a": StageState.SUCCEEDED, "clarify": StageState.SKIPPED, "b": StageState.PENDING}
    assert g.ready(states) == ["b"]
    assert g.evaluate_condition("clarify", {"ambiguous": False}) is False
    assert g.evaluate_condition("clarify", {"ambiguous": True}) is True
    assert g.evaluate_condition("a", {}) is True  # unconditional stages always run


@pytest.mark.req("FR-O14")
def test_downstream_closure() -> None:
    g = diamond()
    assert g.downstream({"b"}) == {"d"}
    assert g.downstream({"a"}) == {"b", "c", "d"}
    assert g.downstream({"d"}) == set()


@pytest.mark.req("FR-O14")
def test_diff_reports_added_removed_and_changed_stages() -> None:
    old = diamond()
    new = WorkflowGraph.build(
        [spec("a"), spec("b", "a"), spec("c", "a", retry_max_attempts=5), spec("e", "b", "c")]
    )
    d = old.diff(new)
    assert d.added == {"e"}
    assert d.removed == {"d"}
    assert d.changed == {"c"}
    assert not d.is_empty


@pytest.mark.req("FR-O14")
def test_diff_of_identical_graphs_is_empty() -> None:
    assert diamond().diff(diamond()).is_empty


@pytest.mark.req("FR-O02", "FR-O06")
def test_graph_serialises_to_plain_data_for_persistence_and_inspection() -> None:
    data = diamond().to_dict()
    assert [s["name"] for s in data["stages"]] == ["a", "b", "c", "d"]
    assert {
        "name",
        "owner",
        "depends_on",
        "retry",
        "timeout_s",
        "fallback",
        "parallel_group",
    } <= set(data["stages"][0])
    assert len(data["edges"]) == 4


@pytest.mark.req("FR-O02")
def test_human_owned_stage_is_a_gate() -> None:
    g = WorkflowGraph.build([spec("a"), spec("approve", "a", owner="human"), spec("b", "approve")])
    assert g.stage("approve").is_gate
    assert not g.stage("a").is_gate
    assert g.gates() == ["approve"]


@pytest.mark.req("FR-O02")
def test_parallel_groups_are_derived_from_shared_dependencies() -> None:
    g = diamond()
    groups = g.parallel_groups()
    assert groups == {"b": "after:a", "c": "after:a"}
