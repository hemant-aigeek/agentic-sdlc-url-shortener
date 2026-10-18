# Quickstart (reviewer)

```bash
git clone https://github.com/hemant-aigeek/agentic-sdlc-url-shortener.git
cd agentic-sdlc-url-shortener
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# quality gate (lint, types, tests, contract drift, licences, secret scan)
./scripts/check.sh

# run the API
agentic-sdlc serve            # http://127.0.0.1:8000/docs

# exercise the shortener
curl -s -X POST localhost:8000/api/v1/links -H 'X-API-Key: dev-key' \
     -H 'content-type: application/json' -d '{"target_url":"https://example.com/a"}'
curl -i localhost:8000/<code>

# run the three scenarios through the orchestrator and export evidence
agentic-sdlc run-scenario greenfield
agentic-sdlc run-scenario brownfield
agentic-sdlc run-scenario ambiguous     # pauses at clarification; follow the printed decide command
agentic-sdlc export-evidence <run_id>   # writes docs/evidence/<run_id>/
```

Full reviewer navigation: `docs/reviewer-guide.md`.
