"""``agentic-sdlc`` command line.

Reviewer-facing entry points. Orchestration commands are added in later task
groups; this module only ever delegates to the planes, it holds no logic.
"""

from __future__ import annotations

import typer

from agentic_sdlc.config import load_settings
from agentic_sdlc.persistence.db import Database

app = typer.Typer(
    help="Agentic SDLC orchestration demonstrated on a URL shortener.", no_args_is_help=True
)


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


if __name__ == "__main__":  # pragma: no cover
    app()
