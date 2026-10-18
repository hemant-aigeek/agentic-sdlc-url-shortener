"""Engine fixtures: in-memory store, scripted test agents, injectable clock and sleep."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import StageError, TransientStageError
from agentic_sdlc.orchestration.agents.base import Agent, AgentRegistry, StageResult
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.graph import StageSpec, WorkflowGraph
from agentic_sdlc.orchestration.store import WorkflowStore
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.workflow_store import SqlWorkflowStore


@dataclass
class Call:
    stage: str
    attempt: int
    started: float
    ended: float = 0.0


@dataclass
class ScriptedAgent(Agent):
    """Records calls; behaviour per stage is scripted by the test."""

    name: str = "scripted"
    sleep_s: float = 0.0
    failures: dict[str, list[Exception]] = field(default_factory=dict)  # stage -> queue of errors
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    compensations: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        call = Call(stage=stage, attempt=attempt, started=time.monotonic())
        with self.lock:
            self.calls.append(call)
        if self.sleep_s:
            time.sleep(self.sleep_s)
        call.ended = time.monotonic()
        queue = self.failures.get(stage)
        if queue:
            raise queue.pop(0)
        out = dict(self.outputs.get(stage, {"done": stage}))
        out["saw_outputs"] = sorted(ctx.outputs)
        return StageResult(
            output=out, artifacts=[(f"{stage}_artifact", {"stage": stage, "attempt": attempt})]
        )

    def compensate(self, ctx: RunContext, stage: str) -> dict[str, Any]:
        with self.lock:
            self.compensations.append(stage)
        return {"compensated": True}


def transient(msg: str = "flaky") -> Exception:
    return TransientStageError(msg)


def permanent(msg: str = "broken") -> Exception:
    return StageError(msg)


@pytest.fixture
def store() -> Iterator[WorkflowStore]:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_all()
    yield SqlWorkflowStore(db)
    db.dispose()


@pytest.fixture
def agent() -> ScriptedAgent:
    return ScriptedAgent()


@pytest.fixture
def settings(tmp_path: Any) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        data_dir=tmp_path / "data",
        retry_base_delay_s=0.01,
        retry_max_delay_s=0.02,
        stage_timeout_s=2.0,
        log_json=False,
    )


def make_engine(
    store: WorkflowStore,
    agent: Agent,
    settings: Settings,
    graphs: dict[str, Callable[[RunContext], WorkflowGraph]],
    **kw: Any,
) -> Engine:
    registry = AgentRegistry({"scripted": agent, "fallback": agent})
    return Engine(store=store, agents=registry, planners=graphs, settings=settings, **kw)


def stage(name: str, *deps: str, **kw: Any) -> StageSpec:
    kw.setdefault("agent", "scripted")
    return StageSpec(name=name, depends_on=tuple(deps), **kw)
