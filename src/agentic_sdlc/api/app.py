"""FastAPI application factory.

``create_app(settings)`` wires both planes. The factory takes explicit settings
so tests can build an isolated app with an in-memory database.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from agentic_sdlc import __version__
from agentic_sdlc.api.problems import install_problem_handlers
from agentic_sdlc.api.ratelimit import TokenBucketLimiter
from agentic_sdlc.api.routers import decisions, health, links, redirect, workflows
from agentic_sdlc.config import Settings, load_settings
from agentic_sdlc.orchestration.agents.base import AgentRegistry
from agentic_sdlc.orchestration.engine import Engine, Planner
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.workflow_store import SqlWorkflowStore
from agentic_sdlc.policy.registry import POLICY_VERSION
from agentic_sdlc.telemetry.logging import bind, configure_logging, unbind

CORRELATION_HEADER = "X-Correlation-ID"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="Agentic SDLC — URL Shortener",
        version=__version__,
        description=(
            "Application plane: URL shortener API (v1). "
            "Control plane: governed, stateful SDLC workflow orchestration."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.db.create_all()
    app.state.limiter = TokenBucketLimiter(
        capacity=settings.rate_limit_capacity,
        refill_per_second=settings.rate_limit_refill_per_second,
    )
    app.state.workflow_store = SqlWorkflowStore(app.state.db)

    def engine_factory(
        agents: AgentRegistry | None = None, planners: dict[str, Planner] | None = None
    ) -> Engine:
        from agentic_sdlc.orchestration.bootstrap import default_agents, default_planners

        return Engine(
            store=app.state.workflow_store,
            agents=agents or default_agents(settings),
            planners=planners or default_planners(),
            settings=settings,
            policy_version=POLICY_VERSION,
        )

    app.state.engine_factory = engine_factory
    app.state.engine = engine_factory()

    @app.middleware("http")
    async def _correlation(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cid = request.headers.get(CORRELATION_HEADER) or uuid.uuid4().hex[:16]
        request.state.correlation_id = cid
        bind(correlation_id=cid)
        try:
            response = await call_next(request)
        finally:
            unbind("correlation_id")
        response.headers[CORRELATION_HEADER] = cid
        return response

    install_problem_handlers(app)
    app.include_router(health.router)
    app.include_router(links.router)
    app.include_router(workflows.router)
    app.include_router(decisions.router)
    # The unversioned redirect catch-all must be registered last.
    app.include_router(redirect.router)
    return app
