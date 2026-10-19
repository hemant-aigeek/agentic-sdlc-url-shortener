# Quickstart (reviewer)

```bash
git clone https://github.com/hemant-aigeek/agentic-sdlc-url-shortener.git
cd agentic-sdlc-url-shortener
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# quality gate (lint, types, tests, contract drift, secret scan, licences)
./scripts/check.sh

# run the API
agentic-sdlc serve            # http://127.0.0.1:8000/docs

# exercise the shortener
curl -s -X POST localhost:8000/api/v1/links -H 'X-API-Key: dev-key' \
     -H 'content-type: application/json' -d '{"target_url":"https://example.com/a"}'
curl -i localhost:8000/<code>

# run the three scenarios through the orchestrator (scripted decisions under your name)
agentic-sdlc scenario run greenfield  --actor you --export /tmp/evidence
agentic-sdlc scenario run brownfield  --actor you --export /tmp/evidence
agentic-sdlc scenario run ambiguous   --actor you --no-decide   # stops at the clarification gate; prints the decide command

# govern a run by hand
agentic-sdlc workflow gates <run_id>
agentic-sdlc workflow decide <run_id> <gate> approve --actor you --reason "..."
agentic-sdlc workflow events <run_id>
agentic-sdlc workflow export-evidence <run_id> --out /tmp/evidence
```

Full reviewer navigation: `docs/reviewer-guide.md`.
