"""Agentic SDLC orchestration demonstrated on a URL shortener.

Two planes in one process:

- ``domain`` / ``api`` / ``persistence.link_repository`` — the application plane
  (the URL shortener).
- ``orchestration`` / ``policy`` / ``persistence.workflow_store`` — the control
  plane (governed, stateful, non-linear SDLC workflow execution).

Import direction between modules is enforced by ``tests/architecture``.
"""

__version__ = "0.1.0"
